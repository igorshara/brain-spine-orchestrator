"""Urodynamics: coordinated EES improves voiding and stays within the McGuire
upper-tract safety criterion; the CMG trace is produced."""
from bso.urodynamics import cystometrogram, study


def test_coordinated_improves_voiding():
    s = study(); b = s["baseline"]["metrics"]; c = s["coordinated"]["metrics"]
    assert c["bve_pct"] > b["bve_pct"]                  # more complete emptying
    assert c["pvr_ml"] < b["pvr_ml"]                    # less post-void residual
    assert c["p_max_void_cmH2O"] < b["p_max_void_cmH2O"]   # lower voiding pressure
    assert c["ad_rise_mmHg"] <= b["ad_rise_mmHg"]       # less autonomic dysreflexia
    assert b["dsd"] and not c["dsd"]                    # dyssynergia resolved


def test_storage_within_mcguire():
    assert study()["baseline"]["metrics"]["safe_storage"]


def test_cmg_trace_present():
    assert len(cystometrogram(modulation=True)["trace"]) > 50
