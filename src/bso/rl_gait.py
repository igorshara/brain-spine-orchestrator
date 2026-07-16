"""Cross-speed gait policy via Evolution Strategies (an RL-family method).

Чесна відповідь на негатив дистиляції (клонування Moco не генералізувало між
швидкостями): тут навчаємо speed-conditioned політику ПРЯМО на gait-обʼєктиві через
Evolution Strategies (Salimans et al. 2017, «ES as a scalable alternative to RL»).
Оскільки ціль (добра хода під втомою) гладка по швидкості, а політика бачить
швидкість, вона має шанс УЗАГАЛЬНИТИ на невидиму швидкість — на відміну від
імітації не-інтерполовних оптимумів.

Gym-style середовище над швидким CPG-симулятором (кінематика). Політика щоінтервал
підлаштовує підсилення ефекторів (компенсує накопичену втому), conditioned на фазі+
швидкості+часі епізоду. Повний PPO/SAC потребував би torch; ES працює в numpy.
Усе ILLUSTRATIVE.
"""

from __future__ import annotations

import math

import numpy as np

from .bus import Bus
from .decoder_stub import IntentEvent
from .degradation import FatigueModel
from .runtime import build_system
from .schemas import Mode

_SWING = ["L_hip_flex", "R_hip_flex", "L_knee_flex", "R_knee_flex",
          "L_ankle_dorsi", "R_ankle_dorsi"]
N_IN, N_HID, N_OUT = 4, 8, 3  # features -> [hip, knee, ankle] gain boosts


class GaitPolicy:
    """Tiny tanh MLP with a flat parameter vector (for ES)."""

    def __init__(self, params=None):
        self.size = N_IN * N_HID + N_HID + N_HID * N_OUT + N_OUT
        self.set_params(np.zeros(self.size) if params is None else np.asarray(params, float))

    def set_params(self, p):
        i = 0
        self.W1 = p[i:i + N_IN * N_HID].reshape(N_IN, N_HID)
        i += N_IN * N_HID
        self.b1 = p[i:i + N_HID]
        i += N_HID
        self.W2 = p[i:i + N_HID * N_OUT].reshape(N_HID, N_OUT)
        i += N_HID * N_OUT
        self.b2 = p[i:i + N_OUT]
        self._p = np.array(p, float)

    def params(self):
        return self._p

    def boosts(self, feats):
        h = np.tanh(feats @ self.W1 + self.b1)
        raw = np.tanh(h @ self.W2 + self.b2)  # -1..1
        return np.clip(1.0 + 0.8 * raw, 0.5, 2.5)  # gain multipliers per joint


class _RLController:
    """Tickable: applies the policy's gain boosts to the swing effectors."""

    def __init__(self, policy, speed, effectors, dur, interval=0.4):
        self.policy, self.speed, self.eff = policy, speed, effectors
        self.dur, self.interval, self._acc = dur, interval, 0.0

    def tick(self, t, dt, bus: Bus):
        self._acc += dt
        if self._acc < self.interval:
            return
        self._acc = 0.0
        gp = bus.latest("gait_phase") or {}
        ph = gp.get("cycle_phase", 0.0)
        feats = np.array([math.sin(2 * math.pi * ph), math.cos(2 * math.pi * ph),
                          self.speed, t / self.dur])
        hip, knee, ankle = self.policy.boosts(feats)
        for g in _SWING:
            b = hip if "hip" in g else (knee if "knee" in g else ankle)
            self.eff.gains[g] = float(b)


def rollout(policy: GaitPolicy, speed: float, dur: float = 9.0) -> float:
    """Run one episode under fatigue at a given speed; reward = retained foot
    clearance + balance (higher = better gait kept against fatigue)."""
    fm = FatigueModel(enabled=True, fatigue_rate=0.10, fatigue_max=0.55, drift_rate_per_s=0.004)
    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=speed)]
    sys_ = build_system(sched, fatigue=fm)
    sys_.loop.add(_RLController(policy, speed, sys_.effectors, dur))
    rec = sys_.run(dur)
    fy = np.array([p["L_foot_y"] for p in rec.pose])
    n = int(2.0 / 0.005)
    cl = [fy[i - n:i].max() - fy[i - n:i].min() for i in range(n, len(fy), n) if rec.t[i] > dur - 5]
    gs = [g for g in rec.gait_state if g is not None]
    bal = sum(g.balance_ok for g in gs) / len(gs) if gs else 0.0
    return float(np.mean(cl)) + 0.1 * bal if cl else 0.0


def es_train(train_speeds, pop=18, elite=5, iters=14, sigma=0.4, seed=0):
    """Evolution Strategies (CEM variant) over policy params, averaged across speeds."""
    rng = np.random.default_rng(seed)
    size = GaitPolicy().size
    mu = np.zeros(size)
    sd = np.full(size, sigma)
    best_p, best_r, hist = mu.copy(), -1e9, []
    for _ in range(iters):
        samples = rng.normal(mu, sd, (pop, size))
        rewards = np.array([np.mean([rollout(GaitPolicy(s), sp) for sp in train_speeds])
                            for s in samples])
        order = np.argsort(rewards)[::-1]
        elite_idx = order[:elite]
        mu = samples[elite_idx].mean(0)
        sd = samples[elite_idx].std(0) + 0.02
        if rewards[order[0]] > best_r:
            best_r, best_p = float(rewards[order[0]]), samples[order[0]].copy()
        hist.append(best_r)
    return best_p, hist
