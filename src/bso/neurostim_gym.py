"""NeuroStim Gym — an open, reproducible benchmark for SCI neurostimulation control.

The field has no standard testbed to *compare* autonomous electrode-mapping and
closed-loop control algorithms before touching a patient. This is that testbed: a small,
seedable, Gym-style environment with standard TASKS, METRICS and BASELINES, plus a
digital-twin pre-optimizer that produces a safe starting program in-silico (cutting
in-clinic programming time).

Design goals (what a research lab actually wants):
  • clean, documented API (reset/step), like an RL gym;
  • tasks that encode the REAL problems — contact selectivity, safe amplitude titration,
    closed-loop adaptation under fatigue;
  • metrics that matter — sample-efficiency (clinician time) and SAFETY violations;
  • reproducible (every result is seeded);
  • baselines so any new algorithm can be compared on equal footing.

This is a SIMULATION/benchmark framework — the environment is illustrative, the value is
the standardized, reproducible methodology. Numbers are not clinical.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from .bopt import bayes_optimize

N_CONTACTS = 16
SAFE_AMP = 14.0          # amplitude (mA, illustrative) above which AD/charge risk rises
FUNC_AMP_RANGE = (4.0, 12.0)   # functional threshold lies in here per patient


# --------------------------------------------------------------------------- tasks
@dataclass
class Patient:
    """A seedable in-silico patient: hidden best contact per goal + functional/safe
    amplitude thresholds. Deterministic given the seed (reproducible benchmarks)."""

    seed: int = 0
    best_contact: int = field(init=False)
    func_amp: float = field(init=False)        # amplitude that achieves function
    width: float = field(init=False)           # recruitment localisation

    def __post_init__(self):
        rng = np.random.default_rng(self.seed)
        self.best_contact = int(rng.integers(0, N_CONTACTS))
        self.func_amp = float(rng.uniform(*FUNC_AMP_RANGE))
        self.width = float(rng.uniform(0.05, 0.09))

    def selectivity(self, contact: int) -> float:
        pos = np.linspace(0, 1, N_CONTACTS)
        d = pos[contact] - pos[self.best_contact]
        return float(np.exp(-(d * d) / (2 * self.width * self.width)))


TASKS = ("contact_mapping", "amplitude_titration", "closed_loop_gait")


class NeuroStimEnv:
    """Gym-style environment. Reset gives an observation; step(action) returns
    (obs, reward, done, info). Three tasks share one API.

    contact_mapping  — action = contact index (0..15); reward = selectivity; the goal
                       is to reach high selectivity in as FEW steps as possible.
    amplitude_titration — action = amplitude (mA); reward rewards reaching the functional
                       threshold but heavily PENALISES exceeding the safety limit.
    closed_loop_gait — action = stim gain (0..1) each tick under drifting fatigue;
                       reward = how close gait output stays to target.
    """

    def __init__(self, task: str = "contact_mapping", seed: int = 0, horizon: int = 20):
        if task not in TASKS:
            raise ValueError(f"unknown task {task!r}; choose from {TASKS}")
        self.task = task
        self.patient = Patient(seed=seed)
        self.horizon = horizon
        self.rng = np.random.default_rng(seed + 1000)
        self.t = 0
        self.safety_violations = 0
        self.best_reward = 0.0
        self._fatigue = 0.0

    # action space description (for documentation / agents)
    @property
    def action_space(self) -> dict:
        if self.task == "contact_mapping":
            return {"type": "discrete", "n": N_CONTACTS}
        if self.task == "amplitude_titration":
            return {"type": "box", "low": 0.0, "high": 20.0}
        return {"type": "box", "low": 0.0, "high": 1.0}

    def reset(self):
        self.t = 0
        self.safety_violations = 0
        self.best_reward = 0.0
        self._fatigue = 0.0
        return self._obs()

    def _obs(self):
        return {"t": self.t, "task": self.task, "fatigue": round(self._fatigue, 3)}

    def step(self, action):
        self.t += 1
        if self.task == "contact_mapping":
            c = int(np.clip(round(action), 0, N_CONTACTS - 1))
            reward = self.patient.selectivity(c)
        elif self.task == "amplitude_titration":
            amp = float(action)
            functional = amp >= self.patient.func_amp
            unsafe = amp >= SAFE_AMP
            if unsafe:
                self.safety_violations += 1
                reward = -1.0
            else:
                reward = 1.0 - abs(amp - self.patient.func_amp) / 12.0 if functional else 0.1
        else:  # closed_loop_gait
            self._fatigue = min(0.6, self._fatigue + 0.05)
            gain = float(np.clip(action, 0, 1))
            # output decays with fatigue unless gain compensates; overshoot wastes charge
            output = gain * (1.0 - self._fatigue)
            target = 0.6
            reward = 1.0 - abs(output - target)
            if gain > 0.95:
                self.safety_violations += 1
                reward -= 0.5
        self.best_reward = max(self.best_reward, reward)
        done = self.t >= self.horizon
        return self._obs(), reward, done, {"safety_violations": self.safety_violations}


# --------------------------------------------------------------------------- agents
def random_agent(env: NeuroStimEnv, seed: int = 0):
    rng = np.random.default_rng(seed)
    sp = env.action_space
    if sp["type"] == "discrete":
        return lambda obs: int(rng.integers(0, sp["n"]))
    return lambda obs: float(rng.uniform(sp["low"], sp["high"]))


def grid_agent(env: NeuroStimEnv):
    sp = env.action_space
    state = {"i": 0}

    def act(obs):
        if sp["type"] == "discrete":
            a = state["i"] % sp["n"]
        else:
            a = sp["low"] + (state["i"] % 10) / 9 * (sp["high"] - sp["low"])
        state["i"] += 1
        return a
    return act


def gpbo_agent(env: NeuroStimEnv, seed: int = 0):
    """Sample-efficient agent: GP-BO over the (discrete or sampled) action set."""
    sp = env.action_space
    if sp["type"] == "discrete":
        cands = np.arange(sp["n"]).reshape(-1, 1).astype(float) / max(1, sp["n"] - 1)
    else:
        cands = np.linspace(sp["low"], sp["high"], 24).reshape(-1, 1)
    plan = {"queue": None, "i": 0}

    def act(obs):
        # precompute the GP-BO query order once using the env as the objective
        if plan["queue"] is None:
            def obj(x):
                a = int(round(x[0] * (sp["n"] - 1))) if sp["type"] == "discrete" else float(x[0])
                # probe a COPY so the real env's counters aren't polluted
                probe = NeuroStimEnv(env.task, seed=env.patient.seed, horizon=1)
                probe.patient = env.patient
                _, r, _, _ = probe.step(a)
                return r
            res = bayes_optimize(obj, cands, n_init=3, n_iter=8, seed=seed)
            plan["queue"] = [cands[i][0] for i in res["queried"]]
        x = plan["queue"][min(plan["i"], len(plan["queue"]) - 1)]
        plan["i"] += 1
        return int(round(x * (sp["n"] - 1))) if sp["type"] == "discrete" else float(x)
    return act


def proportional_agent(env: NeuroStimEnv):
    """A simple closed-loop baseline for the gait task (raises gain with fatigue)."""
    return lambda obs: min(0.92, 0.6 + obs.get("fatigue", 0) * 0.6)


def thompson_agent(env: NeuroStimEnv, seed: int = 0):
    """Thompson-sampling bandit — a principled, classic alternative to GP-BO. Shows the
    benchmark compares MULTIPLE smart algorithms on equal footing, not just one."""
    rng = np.random.default_rng(seed)
    sp = env.action_space
    arms = (np.arange(sp["n"]) if sp["type"] == "discrete"
            else np.linspace(sp["low"], sp["high"], 24))
    mean = np.full(len(arms), 0.5)      # posterior mean per arm
    n = np.zeros(len(arms))
    last = {"i": 0}

    def act(obs):
        # sample each arm's value (Gaussian posterior, shrinking with observations)
        samples = mean + rng.normal(0, 1, len(arms)) / np.sqrt(n + 1)
        i = int(np.argmax(samples))
        last["i"] = i
        a = arms[i]
        return int(a) if sp["type"] == "discrete" else float(a)

    def update(reward):
        i = last["i"]
        n[i] += 1
        mean[i] += (reward - mean[i]) / n[i]
    act.update = update
    return act


# --------------------------------------------------------------------------- runner
def run_episode(env: NeuroStimEnv, policy: Callable) -> dict:
    obs = env.reset()
    total, steps_to_target = 0.0, env.horizon
    target = 0.9 if env.task == "contact_mapping" else 0.8
    hit = False
    for _ in range(env.horizon):
        a = policy(obs)
        obs, r, done, info = env.step(a)
        if hasattr(policy, "update"):
            policy.update(r)           # let learning agents (e.g. Thompson) see the reward
        total += r
        if not hit and r >= target:
            steps_to_target = env.t
            hit = True
        if done:
            break
    return {"return": round(total, 3), "steps_to_target": steps_to_target,
            "safety_violations": env.safety_violations, "hit": hit}


AGENTS = {
    "random": lambda env, s: random_agent(env, s),
    "grid": lambda env, s: grid_agent(env),
    "thompson": lambda env, s: thompson_agent(env, s),
    "gp_bo": lambda env, s: gpbo_agent(env, s),
}


def benchmark(tasks=TASKS, n_patients: int = 12,
              agents=("random", "grid", "thompson", "gp_bo")) -> dict:
    """Evaluate each agent on each task across `n_patients` seeded patients.
    Returns a reproducible scorecard: mean steps-to-target and safety violations."""
    score = {}
    for ag in agents:
        per_task = {}
        for task in tasks:
            steps, viol, hits = [], [], []
            for seed in range(n_patients):
                env = NeuroStimEnv(task, seed=seed)
                aseed = seed * 7919 + 13          # decorrelate agent RNG from the patient
                pol = (proportional_agent(env) if (ag == "gp_bo" and task == "closed_loop_gait")
                       else AGENTS[ag](env, aseed))
                r = run_episode(env, pol)
                steps.append(r["steps_to_target"])
                viol.append(r["safety_violations"])
                hits.append(1 if r["hit"] else 0)
            per_task[task] = {"steps_to_target": round(float(np.mean(steps)), 2),
                              "safety_violations": round(float(np.mean(viol)), 2),
                              "hit_rate": round(float(np.mean(hits)), 2)}
        score[ag] = per_task
    return {"tasks": list(tasks), "n_patients": n_patients, "agents": list(agents),
            "scorecard": score}


def digital_twin_preoptimize(patient_seed: int = 0, goals=("walk", "stand", "bladder")) -> dict:
    """Flight-simulator: run GP-BO in-silico for a patient BEFORE the clinic, producing a
    safe starting program (best contact + functional amplitude) per goal and the number of
    in-silico probes it took. The clinician then refines from this — saving bench time."""
    out = []
    total_probes = 0
    for g in goals:
        # each goal targets a different (seed-shifted) recruitment profile
        env = NeuroStimEnv("contact_mapping", seed=patient_seed + hash(g) % 97)
        pol = gpbo_agent(env, seed=patient_seed)
        rc = run_episode(env, pol)
        env2 = NeuroStimEnv("amplitude_titration", seed=patient_seed + hash(g) % 97)
        pol2 = gpbo_agent(env2, seed=patient_seed)
        ra = run_episode(env2, pol2)
        probes = rc["steps_to_target"] + ra["steps_to_target"]
        total_probes += probes
        out.append({"goal": g, "best_contact": env.patient.best_contact + 1,
                    "func_amp": round(env.patient.func_amp, 1),
                    "probes": probes, "safe": ra["safety_violations"] == 0})
    return {"patient": patient_seed, "programs": out,
            "total_insilico_probes": total_probes,
            "note": "Starting programs computed in-silico; clinician refines on the patient."}
