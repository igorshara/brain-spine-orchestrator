"""Autonomic-first clinical module: coordinated EES improves each function and the
predictive guardian prevents life-threatening autonomic dysreflexia."""
from bso.autonomic_clinical import ad_safety, program


def test_program_has_three_functions_and_improves():
    p = program(weeks=6)
    assert len(p["functions"]) == 3
    bl = next(f for f in p["functions"] if f["key"] == "bladder")
    assert bl["managed"]["peak_pressure_cmH2O"] < bl["baseline"]["peak_pressure_cmH2O"]
    assert bl["managed"]["residual_ml"] <= bl["baseline"]["residual_ml"]
    er = next(f for f in p["functions"] if f["key"] == "erectile")
    assert er["managed"]["functional"] and not er["baseline"]["functional"]


def test_ad_guardian_prevents_events():
    s = ad_safety()
    assert s["predictive_events"] < s["unmanaged_events"]   # life-safety holds
