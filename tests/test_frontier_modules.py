"""Frontier modules: cohort cold-start, recovery-optimizer, multimodal fusion,
telemetry adapter — the capabilities added from the world-frontier scan."""
from bso import cohort_model, fusion, recovery_optimizer, telemetry


def test_cohort_coldstart_lift():
    s = cohort_model.summary(n_cohort=16)
    assert s["warm_zero_pct"] > s["cold_zero_pct"]      # cohort prior helps at ZERO probes
    assert len(s["suggested"]) > 0


def test_recovery_first_beats_function_first():
    r = recovery_optimizer.compare()
    assert r["final_recovery_first"] > r["final_function_first"]   # optimises lasting recovery
    assert r["recovery_gain_pct"] > 0


def test_fusion_beats_best_single_and_survives_dropout():
    f = fusion.demo()
    assert f["fused"] >= f["best_single"] - 1e-9        # fusion ≥ best single modality
    assert f["fused_with_dropout"] > 1 / 3              # better than chance after a dropped channel


def test_telemetry_read_only_with_contract():
    src = telemetry.get_source("simulated")
    assert src.info()["writable"] is False             # BSO never commands the implant
    s = src.read()
    assert len(s.channels) == 16
    c = telemetry.contract()
    assert "read-only" in c["direction"]
    assert "never writes" in c["safety_boundary"]
