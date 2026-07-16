"""Hill-type muscle tests: activation dynamics, force-length, force-velocity,
and that a muscle-driven body still produces stable gait."""

from __future__ import annotations

import numpy as np

from bso.biomech.kinematic import KinematicModel
from bso.decoder_stub import IntentEvent
from bso.muscle import HillMuscle
from bso.runtime import build_system
from bso.schemas import Mode


def test_activation_dynamics_lag_and_asymmetry():
    m = HillMuscle()
    # Rise toward 1.0 — should be gradual, not instant.
    for _ in range(5):
        m.update_activation(1.0, 0.005)
    rising = m.activation
    assert 0.0 < rising < 1.0
    m.update_activation(1.0, 0.5)  # let it saturate
    high = m.activation
    # Deactivation is slower than activation: after equal dt, less change down.
    a1 = HillMuscle()
    a1.activation = 0.5
    a1.update_activation(1.0, 0.01)
    up = a1.activation - 0.5
    a2 = HillMuscle()
    a2.activation = 0.5
    a2.update_activation(0.0, 0.01)
    down = 0.5 - a2.activation
    assert up > down, "activation should be faster than deactivation"
    assert high > 0.9


def test_force_length_peaks_at_optimal():
    m = HillMuscle()
    m.activation = 1.0
    f_opt = m.force(m.opt_length, 0.0)
    f_short = m.force(m.opt_length - 0.4, 0.0)
    f_long = m.force(m.opt_length + 0.4, 0.0)
    assert f_opt > f_short and f_opt > f_long


def test_force_velocity_concentric_weaker_eccentric_stronger():
    m = HillMuscle()
    m.activation = 1.0
    iso = m.force(m.opt_length, 0.0)
    concentric = m.force(m.opt_length, 3.0)   # shortening
    eccentric = m.force(m.opt_length, -3.0)   # lengthening
    assert concentric < iso < eccentric


def test_muscle_driven_gait_is_stable():
    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]
    rec = build_system(sched, model=KinematicModel(use_muscles=True)).run(10.0)
    fy = np.array([p["L_foot_y"] for p in rec.pose[1000:]])
    grfL = np.array([f.grf["L"] for f in rec.frames[1000:] if f])
    grfR = np.array([f.grf["R"] for f in rec.frames[1000:] if f])
    gs = [g for g in rec.gait_state if g is not None]
    assert fy.max() - fy.min() > 0.03, "muscle-driven foot still clears the ground"
    assert np.corrcoef(grfL, grfR)[0, 1] < -0.3, "stance alternates"
    assert sum(g.balance_ok for g in gs) / len(gs) > 0.9


def test_muscle_mode_does_not_change_default():
    # Default model is unchanged (no muscles) — guards the existing behaviour.
    m = KinematicModel()
    assert m.use_muscles is False and not m._muscles
