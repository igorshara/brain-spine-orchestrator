"""Layer-4 adaptation tests — the differentiator.

Доводять: (1) деградація без адаптації псує ходу; (2) адаптація компенсує —
утримує більший кліренс стопи; (3) адаптація не порушує safety; (4) без
деградації адаптація майже не чіпає підсилень.
"""

from __future__ import annotations

import numpy as np

from bso.config.limits import LIMITS
from bso.decoder_stub import IntentEvent
from bso.degradation import FatigueModel
from bso.runtime import build_system
from bso.schemas import Mode

DUR = 24.0
SCHED = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]


def _fatigue():
    return FatigueModel(enabled=True, fatigue_rate=0.09, fatigue_max=0.5,
                        drift_rate_per_s=0.004)


def _late_clearance(rec):
    fy = np.array([p["L_foot_y"] for p in rec.pose])
    n = int(2.0 / 0.005)
    vals = [fy[i - n : i].max() - fy[i - n : i].min()
            for i in range(n, len(fy), n) if rec.t[i] > DUR - 6]
    return float(np.mean(vals))


def test_degradation_reduces_clearance():
    nominal = build_system(SCHED).run(DUR)
    degraded = build_system(SCHED, fatigue=_fatigue()).run(DUR)
    assert _late_clearance(degraded) < _late_clearance(nominal) * 0.8


def test_adaptation_recovers_clearance_vs_no_adaptation():
    degraded = build_system(SCHED, fatigue=_fatigue()).run(DUR)
    adapted = build_system(SCHED, fatigue=_fatigue(), adapt=True).run(DUR)
    assert _late_clearance(adapted) > _late_clearance(degraded) * 1.2, (
        "adaptation should retain meaningfully more foot clearance"
    )


def test_adaptation_raises_gains_under_fatigue():
    adapted = build_system(SCHED, fatigue=_fatigue(), adapt=True).run(DUR)
    assert adapted.gains[-1]["L_knee_flex"] > 1.2


def test_adaptation_idle_when_no_degradation():
    adapted = build_system(SCHED, adapt=True).run(DUR)
    # With no fatigue, achieved tracks desired, so gains stay near 1.0.
    final = adapted.gains[-1]
    assert all(abs(v - 1.0) < 0.3 for v in final.values())


def test_adaptation_never_violates_safety():
    adapted = build_system(SCHED, fatigue=_fatigue(), adapt=True).run(DUR)
    for cmds in adapted.applied:
        for c in cmds:
            assert c.amplitude_mA <= LIMITS.amplitude_max_mA + 1e-9
            assert c.charge_per_phase_uC <= LIMITS.charge_per_phase_max_uC + 1e-9


def test_fatigue_recovers_at_rest():
    fm = _fatigue()
    # Drive use, then rest, and confirm fatigue decreases during rest.
    for _ in range(2000):
        fm.update("L_knee_flex", use=0.9, dt=0.005)
    hot = fm.level("L_knee_flex")
    for _ in range(4000):
        fm.update("L_knee_flex", use=0.0, dt=0.005)
    assert fm.level("L_knee_flex") < hot
