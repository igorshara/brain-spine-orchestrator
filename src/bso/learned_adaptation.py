"""Layer 4, learned — a small policy that LEARNS to compensate degradation.

Шар 4, навчана версія. Замість рукотворного інтегрального контролера тут мала
нейрополітика (numpy MLP), що з локальних СПОСТЕРЕЖУВАНИХ ознак кожної групи
(помилка «задано-досягнуто», поточне підсилення, тренд помилки) обирає корекцію
підсилення. Політика навчається офлайн методом cross-entropy (CEM) проти
симулятора — це і є наш диференціатор: адаптивний агент, а не правило.

КРИТИЧНО (канон §1.6): навчання — ОФЛАЙН, між сесіями. У реальному часі політика
лише робить повільні корекції підсилень (між циклами), не в ms-петлі; safety все
одно обрізає результат. Жодного LLM. Детерміновано за seed.
"""

from __future__ import annotations

import json

import numpy as np

from .bus import Bus

# Observation features per muscle group (all observable — no hidden fatigue):
#   [avg_err (desired-achieved), gain-1.0, err_trend, bias]
N_FEATURES = 4


class MLPPolicy:
    """Tiny tanh MLP: features -> gain-delta. Weights are a flat vector so a
    black-box optimizer (CEM) can search them."""

    def __init__(self, n_hidden: int = 6, params: np.ndarray | None = None) -> None:
        self.n_in = N_FEATURES
        self.n_hidden = n_hidden
        self.size = self.n_in * n_hidden + n_hidden + n_hidden + 1
        self.set_params(np.zeros(self.size) if params is None else np.asarray(params, float))

    def set_params(self, p: np.ndarray) -> None:
        assert len(p) == self.size, f"expected {self.size} params, got {len(p)}"
        i = 0
        self.W1 = p[i : i + self.n_in * self.n_hidden].reshape(self.n_in, self.n_hidden)
        i += self.n_in * self.n_hidden
        self.b1 = p[i : i + self.n_hidden]
        i += self.n_hidden
        self.W2 = p[i : i + self.n_hidden]
        i += self.n_hidden
        self.b2 = p[i]
        self._p = np.array(p, float)

    def params(self) -> np.ndarray:
        return self._p

    def delta(self, features: np.ndarray) -> float:
        h = np.tanh(features @ self.W1 + self.b1)
        return float(h @ self.W2 + self.b2)

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump({"n_hidden": self.n_hidden, "params": self._p.tolist()}, f)

    @classmethod
    def load(cls, path: str) -> MLPPolicy:
        with open(path) as f:
            d = json.load(f)
        return cls(n_hidden=d["n_hidden"], params=np.array(d["params"], float))


class LearnedAdaptation:
    """Layer 4 component driven by an MLPPolicy. Same plug as OnlineAdaptation."""

    IN_TARGETS = "muscle_targets"
    IN_ACT = "activations"
    OUT_TELEMETRY = "adaptation"

    def __init__(self, effectors, policy: MLPPolicy, interval: float = 0.4,
                 step_scale: float = 0.3, gain_min: float = 0.5, gain_max: float = 3.0) -> None:
        self.effectors = effectors
        self.policy = policy
        self.interval = interval
        self.step_scale = step_scale
        self.gain_min = gain_min
        self.gain_max = gain_max
        self._sum_err: dict[str, float] = {}
        self._weight: dict[str, float] = {}
        self._prev_err: dict[str, float] = {}
        self._accum_t = 0.0

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        targets = bus.latest(self.IN_TARGETS) or []
        achieved = bus.latest(self.IN_ACT) or {}
        for mt in targets:
            d = mt.desired_activation
            if d <= 0.1:
                continue
            a = achieved.get(mt.group_id, 0.0)
            self._sum_err[mt.group_id] = self._sum_err.get(mt.group_id, 0.0) + (d - a) * d
            self._weight[mt.group_id] = self._weight.get(mt.group_id, 0.0) + d

        self._accum_t += dt
        if self._accum_t < self.interval:
            return
        self._accum_t = 0.0
        for gid, w in self._weight.items():
            if w <= 1e-6:
                continue
            avg_err = self._sum_err.get(gid, 0.0) / w
            gain = self.effectors.gains.get(gid, 1.0)
            trend = avg_err - self._prev_err.get(gid, avg_err)
            feats = np.array([avg_err, gain - 1.0, trend, 1.0])
            gain += self.step_scale * self.policy.delta(feats)
            self.effectors.gains[gid] = max(self.gain_min, min(self.gain_max, gain))
            self._prev_err[gid] = avg_err
        self._sum_err.clear()
        self._weight.clear()
        bus.publish(self.OUT_TELEMETRY, dict(self.effectors.gains))


# --------------------------------------------------------------------------- #
#  Offline training: cross-entropy method (CEM) — pure numpy, no heavy deps.   #
# --------------------------------------------------------------------------- #

def mean_fatigue(rec) -> float:
    """Average plant fatigue over the session (0 if no fatigue model)."""
    vals = [np.mean(list(f.values())) for f in rec.fatigue if f]
    return float(np.mean(vals)) if vals else 0.0


def _clearance_reward(rec, dur: float, target_clearance: float = 0.14) -> float:
    """Reward = swing-foot clearance toward a healthy TARGET (overshoot earns no
    extra credit — it only wastes stimulation) + balance, minus safety abuse."""
    fy = np.array([p["L_foot_y"] for p in rec.pose])
    n = int(2.0 / 0.005)
    cl = [min(target_clearance, fy[i - n : i].max() - fy[i - n : i].min())
          for i in range(n, len(fy), n) if rec.t[i] > 4]
    mean_cl = float(np.mean(cl)) if cl else 0.0
    gs = [g for g in rec.gait_state if g is not None]
    balance = sum(g.balance_ok for g in gs) / len(gs) if gs else 0.0
    return mean_cl + 0.1 * balance - 0.0005 * len(rec.safety_events)


def evaluate_policy(params, conditions, dur: float = 16.0, n_hidden: int = 6) -> float:
    """Mean reward of a policy across training conditions (fast kinematic body).

    ``conditions`` is a list of callables, each returning a fresh ``build_system``
    kwargs dict (e.g. {"fatigue": FatigueModel(...), "coupling": 0.3}).
    """
    from .runtime import build_system

    policy = MLPPolicy(n_hidden=n_hidden, params=params)
    rewards = []
    for make_cfg in conditions:
        rec = build_system(_train_schedule(), policy=policy, **make_cfg()).run(dur)
        rewards.append(_clearance_reward(rec, dur))
    return float(np.mean(rewards))


def _train_schedule():
    from .decoder_stub import IntentEvent
    from .schemas import Mode

    return [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]


def train_cem(conditions, n_hidden: int = 6, pop: int = 20, elite: int = 5,
              iters: int = 12, init_sigma: float = 0.5, seed: int = 0, dur: float = 16.0):
    """Cross-entropy-method search over policy weights. Returns (best_params,
    history of best reward per iteration)."""
    rng = np.random.default_rng(seed)
    size = MLPPolicy(n_hidden=n_hidden).size
    mu = np.zeros(size)
    sigma = np.full(size, init_sigma)
    best_params, best_reward = mu.copy(), -1e9
    history = []
    for _ in range(iters):
        samples = rng.normal(mu, sigma, size=(pop, size))
        rewards = np.array([evaluate_policy(s, conditions, dur, n_hidden) for s in samples])
        order = np.argsort(rewards)[::-1]
        elite_idx = order[:elite]
        mu = samples[elite_idx].mean(axis=0)
        sigma = samples[elite_idx].std(axis=0) + 0.02
        if rewards[order[0]] > best_reward:
            best_reward = float(rewards[order[0]])
            best_params = samples[order[0]].copy()
        history.append(best_reward)
    return best_params, history
