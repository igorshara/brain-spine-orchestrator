"""Recovery-optimizing control — optimize HEALING, not just function-with-stim-ON.

Найглибший reframe (ідея 1 з vision): поле оптимізує функцію «зі стимуляцією ON».
А справжня ціль — ВІДНОВЛЕННЯ: покращення, що лишається з ВИМКНЕНОЮ стимуляцією.
a landmark study/leading researchers бачили таке нейровідновлення як побічний ефект; ми робимо його ЦІЛЛЮ.

Модель активність-залежної пластичності (ILLUSTRATIVE): сила збереженого спинального
шляху R зростає, коли стимуляція ДОБРЕ ЗЧЕПЛЕНА в часі з наміром→рухом (STDP-вікно),
і згасає від невикористання. Контролер, що оптимізує R (а не миттєву функцію),
знаходить ІНШІ — кращі для довгострокового зцілення — протоколи. Не клінічні дані;
суть — у переосмисленні цілі та доказі, що це дає інші протоколи.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class PlasticityModel:
    """Activity-dependent recovery of a spared pathway. R in [0,1].

    Pairing quality q(timing) peaks at a patient-specific optimal pre-post delay
    (STDP window). dR = lr*q*dose*(1-R) - decay*R per training session.
    """

    tau_opt_ms: float = 20.0     # patient-specific optimal stim timing (hidden)
    width_ms: float = 18.0       # STDP window width
    lr: float = 0.16             # plasticity learning rate
    decay: float = 0.015         # disuse decay per session
    R: float = 0.05              # current recovery (voluntary control, stim OFF)

    def pairing_quality(self, timing_ms: float) -> float:
        return math.exp(-0.5 * ((timing_ms - self.tau_opt_ms) / self.width_ms) ** 2)

    def train_session(self, timing_ms: float, dose: float) -> float:
        q = self.pairing_quality(timing_ms)
        self.R += self.lr * q * max(0.0, min(1.0, dose)) * (1 - self.R) - self.decay * self.R
        self.R = max(0.0, min(1.0, self.R))
        return self.R

    def function_off(self) -> float:
        """Voluntary function with stimulation OFF (the real recovery outcome)."""
        return self.R

    def function_on(self, assist: float) -> float:
        """Function with stimulation ON = recovery + immediate assist (compensation)."""
        return min(1.0, self.R + assist)


def function_first_course(n_sessions=30, assist=0.6, bad_timing_ms=70.0, **mk):
    """Maximize immediate stim-ON function: crank assist, ignore timing -> poor
    pairing -> little real recovery. Returns R trajectory (stim-OFF function)."""
    m = PlasticityModel(**mk)
    traj = []
    for _ in range(n_sessions):
        m.train_session(timing_ms=bad_timing_ms, dose=1.0)
        traj.append(m.function_off())
    return traj, m.function_on(assist)


def use_driven_session(m: "PlasticityModel", timing_ms: float, assist: float,
                       beta: float = 1.0) -> float:
    """One training session under the USE-DRIVEN hypothesis: the plasticity dose
    is the patient's OWN contribution, not the machine's.

    Two competing effects of the assist level a in [0,1]:
      - movement success rises with assist — the limb must actually complete the
        motion to generate the sensory volley that pairs with the command;
      - engagement (use-dependent drive) rises with the patient's self-fraction
        (1-a) — if the machine does everything, the patient's circuits barely fire.
    Effective dose = success * engagement, so neither full assist nor zero assist
    is optimal: there is an interior best (assist-as-needed).
    """
    success = min(1.0, m.R + max(0.0, min(1.0, assist)))
    engagement = max(0.0, 1.0 - assist) ** beta
    return m.train_session(timing_ms=timing_ms, dose=success * engagement)


def use_driven_course(assist: float, n_sessions: int = 40, timing_ms: float = 20.0,
                      beta: float = 1.0, adaptive: bool = False, **mk):
    """Run a course at a FIXED assist, or (adaptive=True) fade assist as recovery
    grows — assist-as-needed a = (1-R)/2. Returns the stim-OFF recovery R(t)."""
    m = PlasticityModel(**mk)
    traj = []
    for _ in range(n_sessions):
        a = (1.0 - m.R) / 2.0 if adaptive else assist
        use_driven_session(m, timing_ms, a, beta)
        traj.append(m.function_off())
    return traj


def optimal_assist(n_sessions: int = 40, timing_ms: float = 20.0, beta: float = 1.0,
                   n: int = 21, **mk) -> dict:
    """Sweep fixed assist 0..1 and report final stim-OFF recovery for each, plus
    the adaptive (fading) protocol. Tests whether the best assist is INTERIOR."""
    assists = [i / (n - 1) for i in range(n)]
    finals = [use_driven_course(a, n_sessions, timing_ms, beta, **mk)[-1] for a in assists]
    best_i = max(range(n), key=lambda i: finals[i])
    adaptive_R = use_driven_course(0.0, n_sessions, timing_ms, beta, adaptive=True, **mk)[-1]
    return {
        "assists": [round(a, 3) for a in assists],
        "final_R": [round(float(x), 4) for x in finals],
        "best_assist": round(assists[best_i], 3),
        "best_R": round(float(finals[best_i]), 4),
        "full_assist_R": round(float(finals[-1]), 4),
        "no_assist_R": round(float(finals[0]), 4),
        "adaptive_R": round(float(adaptive_R), 4),
        "note": "R = voluntary function with stimulation OFF (lasting recovery).",
    }


def recovery_first_course(n_sessions=30, explore=6, seed=0, **mk):
    """Maximize RECOVERY: spend early sessions discovering the patient's optimal
    stim timing (it is unknown), then exploit it -> strong real recovery."""
    import numpy as np
    rng = np.random.default_rng(seed)
    m = PlasticityModel(**mk)
    traj = []
    candidates = list(np.linspace(-20, 80, 8))
    scores = {c: 0.0 for c in candidates}
    best = candidates[0]
    for s in range(n_sessions):
        if s < explore:  # probe timings, judge by the session's recovery increment
            c = candidates[s % len(candidates)]
            before = m.R
            m.train_session(timing_ms=c, dose=1.0)
            scores[c] = m.R - before
            best = max(scores, key=scores.get)
        else:            # exploit the best-found timing
            m.train_session(timing_ms=best + float(rng.normal(0, 2)), dose=1.0)
        traj.append(m.function_off())
    return traj, best
