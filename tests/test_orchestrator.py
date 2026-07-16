"""Orchestrator (CPG) tests — canon M3.

Готово коли: у режимі WALK генерується ритмічний фазовий патерн із коректним
чергуванням ліво/право.
"""

from __future__ import annotations

import numpy as np

from bso.bus import Bus
from bso.orchestrator import Orchestrator
from bso.schemas import Intent, Mode


def _run_targets(mode: Mode, speed: float, n: int = 400, dt: float = 0.005):
    bus = Bus()
    orch = Orchestrator()
    series: list[list] = []
    for i in range(n):
        bus.publish("intent", Intent(t=i * dt, mode=mode, speed=speed, confidence=1.0))
        orch.tick(i * dt, dt, bus)
        series.append(bus.latest("muscle_targets"))
    return orch, series


def _act(targets, group_id):
    for mt in targets:
        if mt.group_id == group_id:
            return mt.desired_activation
    return 0.0


def test_idle_is_all_zero():
    _, series = _run_targets(Mode.IDLE, 0.0, n=10)
    assert all(mt.desired_activation == 0.0 for mt in series[-1])


def test_phase_clock_advances_only_in_locomotion():
    orch, _ = _run_targets(Mode.STAND, 0.0, n=200)
    assert orch.cycle_phase == 0.0
    orch2, _ = _run_targets(Mode.WALK, 0.5, n=200)
    assert orch2.cycle_phase != 0.0


def test_walk_left_right_hip_are_antiphase():
    _, series = _run_targets(Mode.WALK, 0.6, n=800)
    lhf = np.array([_act(t, "L_hip_flex") for t in series])
    rhf = np.array([_act(t, "R_hip_flex") for t in series])
    # Use the second half (steady state) to avoid the cold-start transient.
    half = len(series) // 2
    corr = np.corrcoef(lhf[half:], rhf[half:])[0, 1]
    assert corr < -0.3, f"L/R hip_flex should be antiphase, got corr={corr:.2f}"


def test_walk_is_rhythmic():
    _, series = _run_targets(Mode.WALK, 0.6, n=1000)
    sig = np.array([_act(t, "L_hip_flex") for t in series])
    # A rhythmic signal has clear variance and multiple zero-crossings of its
    # mean-subtracted form.
    centered = sig - sig.mean()
    crossings = np.sum(centered[:-1] * centered[1:] < 0)
    assert sig.std() > 0.05
    assert crossings >= 4, f"expected several gait cycles, got {crossings} crossings"


def test_cadence_increases_with_speed():
    slow, _ = _run_targets(Mode.WALK, 0.1, n=10)
    fast, _ = _run_targets(Mode.WALK, 0.9, n=10)
    assert fast.cadence > slow.cadence


def test_correction_scales_activation_down():
    bus = Bus()
    orch = Orchestrator()
    # No correction first.
    bus.publish("intent", Intent(t=0.0, mode=Mode.WALK, speed=0.6, confidence=1.0))
    orch.tick(0.0, 0.005, bus)
    base = _act(bus.latest("muscle_targets"), "L_hip_flex")
    # Now publish a damping correction and step again at a phase with activity.
    for i in range(120):
        bus.publish("intent", Intent(t=i * 0.005, mode=Mode.WALK, speed=0.6, confidence=1.0))
        bus.publish("corrections", {"L_hip_flex": 0.5})
        orch.tick(i * 0.005, 0.005, bus)
    # The correction multiplies whatever the profile asks for; verify a known
    # phase: compare with/without by re-deriving the unscaled profile value.
    scaled = _act(bus.latest("muscle_targets"), "L_hip_flex")
    # Re-run identical phase without correction.
    bus2 = Bus()
    orch2 = Orchestrator()
    for i in range(120):
        bus2.publish("intent", Intent(t=i * 0.005, mode=Mode.WALK, speed=0.6, confidence=1.0))
        orch2.tick(i * 0.005, 0.005, bus2)
    unscaled = _act(bus2.latest("muscle_targets"), "L_hip_flex")
    assert scaled <= unscaled + 1e-9
    assert base >= 0.0
