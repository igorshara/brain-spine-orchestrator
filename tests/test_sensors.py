"""Sensor-corruption tests (kinematic backend — no MuJoCo needed).

Перевіряють детермінізм псування за seed і що замкнутий контур лишається стабільним
під шумом/дропаутом сенсорів.
"""

from __future__ import annotations

import numpy as np

from bso.decoder_stub import IntentEvent
from bso.runtime import build_system
from bso.schemas import Mode, SensorFrame
from bso.sensors import SensorCorruptor

SCHED = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]


class _Bus:
    def __init__(self):
        self._d = {}

    def publish(self, topic, msg):
        self._d[topic] = msg

    def latest(self, topic, default=None):
        return self._d.get(topic, default)


def test_corruptor_is_deterministic_per_seed():
    frame = SensorFrame(t=0.0, joint_angles={"L_hip": 10.0}, grf={"L": 300.0, "R": 0.0})
    a, b = SensorCorruptor(noise_deg=3.0, seed=42), SensorCorruptor(noise_deg=3.0, seed=42)
    ba, bb = _Bus(), _Bus()
    ba.publish("sensor_frame", frame)
    bb.publish("sensor_frame", frame)
    a.tick(0.0, 0.005, ba)
    b.tick(0.0, 0.005, bb)
    assert ba.latest("sensor_frame").joint_angles["L_hip"] == \
        bb.latest("sensor_frame").joint_angles["L_hip"]


def test_corruptor_adds_noise():
    frame = SensorFrame(t=0.0, joint_angles={"L_hip": 10.0}, grf={"L": 300.0, "R": 0.0})
    c = SensorCorruptor(noise_deg=5.0, seed=7)
    bus = _Bus()
    bus.publish("sensor_frame", frame)
    c.tick(0.0, 0.005, bus)
    assert bus.latest("sensor_frame").joint_angles["L_hip"] != 10.0


def test_closed_loop_stable_under_sensor_noise():
    corr = SensorCorruptor(noise_deg=2.0, noise_grf_N=40.0, dropout_prob=0.05, seed=3)
    rec = build_system(SCHED, sensor_corruptor=corr).run(10.0)
    gs = [g for g in rec.gait_state if g is not None]
    # Balance largely maintained and the foot still lifts despite noisy feedback.
    assert sum(g.balance_ok for g in gs) / len(gs) > 0.85
    fy = np.array([p["L_foot_y"] for p in rec.pose[1000:]])
    assert fy.max() - fy.min() > 0.03


def test_full_dropout_does_not_crash():
    corr = SensorCorruptor(dropout_prob=1.0, seed=1)
    rec = build_system(SCHED, sensor_corruptor=corr).run(4.0)
    assert len(rec.t) > 0
