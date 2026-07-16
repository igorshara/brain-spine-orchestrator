"""Recovery-optimizing orchestrator — plasticity as the objective.

Most stimulation optimises immediate movement (a permanent crutch). This module
flips the objective: choose stimulation timing/dose to maximise LASTING recovery —
voluntary function with the stimulation OFF — by exploiting activity-dependent
plasticity (Hebbian/STDP-style pairing). Backed by emerging evidence that precisely
timed stimulation + rehab drives durable plasticity (e.g. closed-loop VNS, Nature
2025). Wraps `plasticity.py`.

Illustrative research simulation — not a medical device.
"""
from __future__ import annotations

from .plasticity import function_first_course, recovery_first_course


def compare(n_sessions: int = 30, seed: int = 0) -> dict:
    """Function-first (assist now, poor pairing) vs recovery-first (find the
    plasticity-optimal timing, then exploit it). Returns the stim-OFF recovery
    trajectory R(t) for each — R is real recovery, measured with stimulation OFF."""
    ff_traj, _ff_on = function_first_course(n_sessions=n_sessions)
    rf_traj, _best = recovery_first_course(n_sessions=n_sessions, seed=seed)
    ff = [round(float(x), 4) for x in ff_traj]
    rf = [round(float(x), 4) for x in rf_traj]
    gain = (rf[-1] - ff[-1]) / ff[-1] * 100 if ff[-1] > 1e-6 else 0.0
    return {
        "sessions": list(range(1, len(rf) + 1)),
        "function_first_R": ff,
        "recovery_first_R": rf,
        "final_function_first": ff[-1],
        "final_recovery_first": rf[-1],
        "recovery_gain_pct": round(gain),
        "note": "R = voluntary function with stimulation OFF (real, lasting recovery).",
    }
