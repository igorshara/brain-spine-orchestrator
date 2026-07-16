"""MuJoCo dynamic-backend tests. Skipped if mujoco is not installed.

Перевіряють, що той самий CPG-конвеєр на динамічному фізичному тілі тримається
вертикально, дає реальну GRF із чергуванням опори й не порушує safety.
"""

from __future__ import annotations

import numpy as np
import pytest

mujoco = pytest.importorskip("mujoco")

from bso.config.limits import LIMITS  # noqa: E402
from bso.decoder_stub import IntentEvent  # noqa: E402
from bso.runtime import build_system  # noqa: E402
from bso.schemas import Mode  # noqa: E402


def _walk(dur=10.0):
    from bso.biomech.mujoco_model import MuJoCoModel

    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(2.0, Mode.WALK, speed=0.45)]
    return build_system(sched, model=MuJoCoModel()).run(dur)


def test_biped_stays_upright():
    rec = _walk()
    n0 = int(4 / 0.005)
    pz = [p["pelvis_z"] for p in rec.pose[n0:]]
    trunk = [abs(p["trunk"]) for p in rec.pose[n0:]]
    assert np.mean(pz) > 0.8, "pelvis collapsed (model fell into a crouch)"
    assert np.percentile(trunk, 95) < 20.0, "trunk lean too large (not upright)"


def test_physics_grf_is_real_and_alternates():
    rec = _walk()
    n0 = int(4 / 0.005)
    grfL = np.array([f.grf["L"] for f in rec.frames[n0:] if f])
    grfR = np.array([f.grf["R"] for f in rec.frames[n0:] if f])
    # GRF should be on the order of body weight, not exploding.
    assert 50 < np.median(grfL[grfL > 0]) < 2000
    assert np.corrcoef(grfL, grfR)[0, 1] < -0.3, "stance does not alternate"


def test_foot_clears_the_ground_each_cycle():
    rec = _walk()
    n0 = int(4 / 0.005)
    fy = np.array([p["L_foot_y"] for p in rec.pose[n0:]])
    assert fy.max() - fy.min() > 0.02, "foot never lifts (no swing clearance)"


def test_safety_holds_under_physics():
    rec = _walk()
    for cmds in rec.applied:
        for c in cmds:
            assert c.amplitude_mA <= LIMITS.amplitude_max_mA + 1e-9
            assert c.charge_per_phase_uC <= LIMITS.charge_per_phase_max_uC + 1e-9


def _late_clearance(rec, dur):
    fy = np.array([p["L_foot_y"] for p in rec.pose])
    n = int(2.0 / 0.005)
    vals = [fy[i - n : i].max() - fy[i - n : i].min()
            for i in range(n, len(fy), n) if rec.t[i] > dur - 4]
    return float(np.mean(vals))


def test_adaptation_helps_on_physics():
    from bso.biomech.mujoco_model import MuJoCoModel
    from bso.degradation import FatigueModel

    def fm():
        return FatigueModel(enabled=True, fatigue_rate=0.09, fatigue_max=0.5,
                            drift_rate_per_s=0.004)

    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(2.0, Mode.WALK, speed=0.45)]
    dur = 16.0
    degraded = build_system(sched, model=MuJoCoModel(), fatigue=fm()).run(dur)
    adapted = build_system(sched, model=MuJoCoModel(), fatigue=fm(), adapt=True).run(dur)
    assert _late_clearance(adapted, dur) > _late_clearance(degraded, dur) * 1.1


def test_active_balance_beats_passive_after_push():
    from bso.biomech.mujoco_model import MuJoCoModel

    def run(active):
        m = MuJoCoModel()
        m.active_balance = active
        sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(2.0, Mode.WALK, speed=0.45)]
        sys_ = build_system(sched, model=m)
        sys_.loop.run(6.0)
        m.perturb(6.0)
        sys_.loop.run(3.0)
        tr = [p["trunk"] for p in sys_.recorder.pose]
        i = int(6 / 0.005)
        return max(abs(x) for x in tr[i:i + 200])

    active_peak = run(True)
    passive_peak = run(False)
    assert active_peak < passive_peak * 0.8, (
        f"active balance should reject the push better: {active_peak:.1f} vs {passive_peak:.1f}"
    )


def test_upright_under_sensor_noise_on_physics():
    from bso.biomech.mujoco_model import MuJoCoModel
    from bso.sensors import SensorCorruptor

    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(2.0, Mode.WALK, speed=0.45)]
    corr = SensorCorruptor(noise_deg=2.0, noise_grf_N=40.0, dropout_prob=0.05, seed=2)
    rec = build_system(sched, model=MuJoCoModel(), adapt=True, sensor_corruptor=corr).run(14.0)
    pz = np.mean([p["pelvis_z"] for p in rec.pose[800:]])
    assert pz > 0.8, "biped collapsed under noisy feedback"
