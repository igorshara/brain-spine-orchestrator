"""Autonomic-first clinical module — a clinician-facing program.

Consolidates the autonomic functions that people with SCI rank as high as, or above,
walking — bladder, bowel, erectile — plus blood-pressure / autonomic dysreflexia
(life-safety) into ONE clinical workflow: baseline assessment → coordinated-EES
protocol → expected outcome → scheduled training → predictive AD guardian. This is
the nearest real-world impact and is a clinically validated direction (peer-reviewed evidence, 2025).

Decision-support only — the clinician decides; every number is illustrative and is
produced by the in-silico models in `autonomic.py`, not asserted.
"""
from __future__ import annotations

from .ad_guardian import simulate as ad_simulate
from .autonomic import (AutonomicCommand, AutonomicOrchestrator, BowelModel,
                        ErectileModel, simulate_bladder)
from .autonomic_training import simulate_training_curve

# Recommended coordinated-EES protocol per function (sacral/lumbar regions).
_PROTOCOL = {
    "bladder": {"region": "S2–S4 (sacral)", "mode": "coordinated low-pressure voiding",
                "freq_hz": 30},
    "bowel": {"region": "S2–S4 (sacral)", "mode": "propulsion + sphincter relaxation",
              "freq_hz": 30},
    "erectile": {"region": "S2–S4 (parasympathetic)", "mode": "para-drive tumescence",
                 "freq_hz": 15},
}


def _bladder() -> dict:
    _b0, ad0, r0 = simulate_bladder(modulation=False)     # dyssynergic baseline
    b1, ad1, r1 = simulate_bladder(modulation=True)       # coordinated
    return {
        "key": "bladder", "title": "Bladder (neurogenic)",
        "baseline": {"peak_pressure_cmH2O": round(max(r0.bladder_pressure)),
                     "residual_ml": round(r0.bladder_volume[-1]),
                     "ad_rise_mmHg": round(ad0.systolic_rise)},
        "managed": {"peak_pressure_cmH2O": round(max(r1.bladder_pressure)),
                    "residual_ml": round(r1.bladder_volume[-1]),
                    "ad_rise_mmHg": round(ad1.systolic_rise)},
        "target": "<40 cmH₂O (the upper-tract criterion), complete emptying, no AD",
        "protocol": _PROTOCOL["bladder"],
        "units": "cmH₂O / mL / mmHg",
    }


def _run_bowel(modulation: bool) -> float:
    m = BowelModel(dyssynergia=not modulation)
    orch = AutonomicOrchestrator(modulation=modulation)
    dt = 0.1
    for i in range(1200):
        cmd = AutonomicCommand.STORE if i < 600 else AutonomicCommand.VOID
        m.step(orch.drive_for(cmd), cmd, dt)
    return m.evacuated


def _bowel() -> dict:
    base, managed = _run_bowel(False), _run_bowel(True)
    return {
        "key": "bowel", "title": "Bowel (neurogenic)",
        "baseline": {"evacuated_index": round(base, 2)},
        "managed": {"evacuated_index": round(managed, 2)},
        "target": "complete, predictable evacuation",
        "protocol": _PROTOCOL["bowel"],
        "units": "evacuation index (a.u., higher = better)",
    }


def _run_erectile(modulation: bool) -> tuple[float, bool]:
    m = ErectileModel()
    orch = AutonomicOrchestrator(modulation=modulation)
    dt = 0.1
    for _ in range(300):
        m.step(orch.drive_for(AutonomicCommand.ENGAGE), AutonomicCommand.ENGAGE, dt)
    return m.pressure, m.functional


def _erectile() -> dict:
    p0, f0 = _run_erectile(False)
    p1, f1 = _run_erectile(True)
    return {
        "key": "erectile", "title": "Erectile function",
        "baseline": {"rigidity": round(p0, 2), "functional": bool(f0)},
        "managed": {"rigidity": round(p1, 2), "functional": bool(f1)},
        "target": "functional rigidity on demand",
        "protocol": _PROTOCOL["erectile"],
        "units": "rigidity 0–1",
    }


def ad_safety() -> dict:
    """Life-safety: predictive autonomic-dysreflexia guardian vs no control."""
    _r0, none = ad_simulate("none")
    _r1, pred = ad_simulate("predictive")
    return {
        "unmanaged_events": none["ad_events"],
        "predictive_events": pred["ad_events"],
        "unmanaged_peak_bp_rise": round(none["peak_bp_rise"]),
        "predictive_peak_bp_rise": round(pred["peak_bp_rise"]),
        "first_warning_s": pred["first_warning_s"],
        "note": "Autonomic dysreflexia is life-threatening; the guardian prevents it predictively.",
    }


def program(weeks: int = 8) -> dict:
    """The full clinician-facing autonomic program."""
    curve = simulate_training_curve(weeks=weeks)
    return {
        "functions": [_bladder(), _bowel(), _erectile()],
        "ad_safety": ad_safety(),
        "training_curve": curve,
        "disclaimer": ("Decision-support, illustrative simulation. Clinician applies on a "
                       "certified device; a clinically validated direction (peer-reviewed "
                       "evidence, 2025)."),
    }
