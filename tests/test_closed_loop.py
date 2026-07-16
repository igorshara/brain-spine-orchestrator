"""Closed-loop integration tests — canon M4.

Готово коли: симульована «хода» стабільна; детектор помилок реагує на збурення.
Also asserts the system-wide safety invariant end-to-end: no command that
reaches the body is ever outside the hard envelope, and e-stop halts motion.
"""

from __future__ import annotations

import numpy as np

from bso.config.limits import LIMITS
from bso.decoder_stub import IntentEvent
from bso.feedback import Feedback
from bso.runtime import build_system
from bso.schemas import Mode, Phase, SensorFrame


def _walk(duration=10.0, speed=0.6):
    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(0.5, Mode.WALK, speed=speed)]
    return build_system(sched).run(duration)


def test_walk_produces_alternating_stance():
    rec = _walk()
    grfL = np.array([f.grf["L"] for f in rec.frames[1000:] if f])
    grfR = np.array([f.grf["R"] for f in rec.frames[1000:] if f])
    corr = np.corrcoef(grfL, grfR)[0, 1]
    assert corr < -0.2, f"L/R stance should alternate, got GRF corr={corr:.2f}"


def test_swing_lifts_the_foot():
    rec = _walk()
    lfy = np.array([p["L_foot_y"] for p in rec.pose[1000:]])
    # Foot must both plant (low) and clear (high) within a cycle.
    assert lfy.max() - lfy.min() > 0.03, "foot does not lift during swing"


def test_walk_is_stable_balance_maintained():
    rec = _walk(duration=12.0)
    gs = [g for g in rec.gait_state if g is not None]
    ratio = sum(g.balance_ok for g in gs) / len(gs)
    assert ratio > 0.9, f"balance lost too often: ok ratio={ratio:.2f}"


def test_no_applied_command_exceeds_envelope():
    rec = _walk()
    for cmds in rec.applied:
        for c in cmds:
            assert c.amplitude_mA <= LIMITS.amplitude_max_mA + 1e-9
            assert c.pulse_width_us <= LIMITS.pulse_width_max_us + 1e-9
            assert c.frequency_Hz <= LIMITS.frequency_max_Hz + 1e-9
            assert c.charge_per_phase_uC <= LIMITS.charge_per_phase_max_uC + 1e-9


def test_estop_mid_run_halts_motion():
    sched = [IntentEvent(0.0, Mode.WALK, speed=0.6)]
    sys = build_system(sched)
    sys.loop.run(4.0)
    moving_pose = sys.recorder.pose[-1]["L_hip"]
    sys.safety.trigger_estop("test halt")
    sys.loop.run(2.0)
    # After e-stop, activations are zero and joints relax toward neutral and stop.
    tail = [p["L_hip"] for p in sys.recorder.pose[-100:]]
    assert np.std(tail) < 1.0, "joints still oscillating after e-stop"
    assert moving_pose is not None


def test_feedback_detects_foot_drag():
    fb = Feedback()
    bus_like = _FakeBus()
    # Swing on the left (low GRF) with a plantarflexed ankle => foot drag.
    frame = SensorFrame(
        t=1.0,
        joint_angles={"L_ankle": -10.0, "trunk": 0.0},
        grf={"L": 0.0, "R": 600.0},
    )
    bus_like.set("sensor_frame", frame)
    fb.tick(1.0, 0.005, bus_like)
    corr = bus_like.latest("corrections")
    assert corr.get("L_ankle_dorsi", 1.0) > 1.0, "foot-drag boost not issued"


def test_feedback_flags_balance_loss():
    fb = Feedback()
    bus_like = _FakeBus()
    frame = SensorFrame(t=1.0, joint_angles={"trunk": 25.0}, grf={"L": 400.0, "R": 400.0})
    bus_like.set("sensor_frame", frame)
    fb.tick(1.0, 0.005, bus_like)
    state = bus_like.latest("gait_state")
    assert state.balance_ok is False
    corr = bus_like.latest("corrections")
    assert corr.get("L_trunk_stab", 1.0) > 1.0


def test_feedback_phase_labels_from_grf():
    fb = Feedback()
    bus_like = _FakeBus()
    frame = SensorFrame(t=1.0, joint_angles={"trunk": 0.0}, grf={"L": 500.0, "R": 0.0})
    bus_like.set("sensor_frame", frame)
    fb.tick(1.0, 0.005, bus_like)
    state = bus_like.latest("gait_state")
    assert state.phase_left == Phase.STANCE
    assert state.phase_right == Phase.SWING


class _FakeBus:
    """Minimal bus stand-in for unit-testing a single component."""

    def __init__(self):
        self._d = {}

    def set(self, topic, msg):
        self._d[topic] = msg

    def publish(self, topic, msg):
        self._d[topic] = msg

    def latest(self, topic, default=None):
        return self._d.get(topic, default)
