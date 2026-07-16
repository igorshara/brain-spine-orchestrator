"""Shadow Step — feed-forward dorsiflexion vs reactive, on the digital twin.

Locks in the IZAR invention-engine finding. On the Hill-muscle twin (where the
muscle's own activation dynamics create a physiological electromechanical delay),
anticipating swing from the CPG phase clock and redistributing dorsiflexion
("shadow step") cuts foot drag with LESS stimulation than correcting only after
a sensed drop. On the instant twin there is no delay to anticipate, so no drag
benefit is required — the mechanism is conditional, and the tests assert exactly
that.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bso.biomech.kinematic import KinematicModel
from bso.decoder_stub import IntentEvent
from bso.feedback import FOOT_DRAG_ANKLE_DEG
from bso.runtime import build_system
from bso.schemas import Mode

DT, DUR, WARMUP = 0.005, 16.0, 4.0
LEAD_MS, PRED_GAIN, PRED_TAIL = 100.0, 1.5, 0.5


def _run(mode: str, hill: bool):
    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]
    model = KinematicModel(use_muscles=True) if hill else KinematicModel()
    sysm = build_system(sched, dt=DT, model=model)
    fb = sysm.feedback
    fb.mode = mode
    fb.lead_ms, fb.pred_gain, fb.pred_tail_gain = LEAD_MS, PRED_GAIN, PRED_TAIL
    rec = sysm.run(DUR)
    drag = swing = 0
    effort = 0.0
    for i, t in enumerate(rec.t):
        if t < WARMUP:
            continue
        gp = rec.gait_phase[i] or {}
        cp = gp.get("cycle_phase")
        if cp is None or gp.get("cadence", 0.0) <= 0.0:
            continue
        pose, act = rec.pose[i], (rec.activations[i] or {})
        effort += act.get("L_ankle_dorsi", 0.0) + act.get("R_ankle_dorsi", 0.0)
        for side, lp in (("L", cp), ("R", (cp + 0.5) % 1.0)):
            if 0.60 <= lp <= 1.0:
                swing += 1
                if pose.get(f"{side}_ankle", 0.0) <= FOOT_DRAG_ANKLE_DEG:
                    drag += 1
    return {"drag": drag, "drag_pct": 100.0 * drag / max(1, swing),
            "effort": effort}


def test_shadow_step_cuts_drag_with_less_stim_on_hill_twin():
    """The headline claim: on the physiological Hill twin, predictive reduces
    foot drag AND uses no more dorsiflexion stimulation than reactive."""
    reactive = _run("reactive", hill=True)
    predictive = _run("predictive", hill=True)
    assert predictive["drag"] < reactive["drag"], (
        f"shadow step should cut drag: pred={predictive['drag']} react={reactive['drag']}")
    assert predictive["effort"] <= reactive["effort"], (
        f"shadow step should not cost more stim: pred={predictive['effort']:.0f} "
        f"react={reactive['effort']:.0f}")


def test_physiological_delay_makes_control_harder():
    """Sanity: the Hill twin's activation dynamics make foot drag worse for the
    same reactive controller than the instant twin — the delay is real."""
    instant = _run("reactive", hill=False)
    hill = _run("reactive", hill=True)
    assert hill["drag"] > instant["drag"]


def test_no_required_drag_benefit_without_delay():
    """On the instant twin there is nothing to anticipate, so the shadow step is
    not required to beat reactive on drag (it must not blow up effort either)."""
    reactive = _run("reactive", hill=False)
    predictive = _run("predictive", hill=False)
    assert predictive["drag"] <= reactive["drag"] + 1   # no worse (±1 tick)
    assert predictive["effort"] <= reactive["effort"] * 1.05


def test_determinism():
    a = _run("predictive", hill=True)
    b = _run("predictive", hill=True)
    assert a == b
