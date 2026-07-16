"""Backend↔frontend contract: responses carry version+source, drift is caught."""
from bso.api_schema import API_VERSION, check_contract, envelope


def test_envelope_adds_version_and_source():
    out = envelope({"metrics": {}}, "real")
    assert out["_meta"]["api_version"] == API_VERSION
    assert out["_meta"]["source"] == "real"
    assert "metrics" in out                       # original keys preserved (non-breaking)


def test_contract_warns_on_missing_key():
    w = check_contract("/api/locomotion", {"frames": []})   # missing 'metrics'
    assert w and "metrics" in w
    assert check_contract("/api/locomotion", {"frames": [], "metrics": {}}) is None


def test_unknown_endpoint_not_checked():
    assert check_contract("/api/unknown", {"x": 1}) is None
