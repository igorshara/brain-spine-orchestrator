"""Scheduled autonomic training — the «discipline the reflex» protocols."""

from __future__ import annotations

from bso.autonomic_training import (
    PROTOCOLS,
    schedule_24h,
    simulate_bladder_day,
    simulate_training_curve,
)


def test_schedule_fires_every_4h():
    sch = schedule_24h()
    bladder_hours = [e["h"] for e in sch["events"] if e["function"] == "bladder"]
    assert bladder_hours == [0, 4, 8, 12, 16, 20]
    assert any(e["function"] == "bowel" for e in sch["events"])


def test_day_voids_at_interval():
    day = simulate_bladder_day(interval_h=4.0)
    assert len(day["voids"]) == 5  # voids at 4,8,12,16,20 h within 24 h


def test_training_reduces_residual_and_ad():
    curve = simulate_training_curve(weeks=8)
    wk = curve["weeks"]
    assert wk[0]["residual_ml"] > wk[-1]["residual_ml"]   # emptying improves
    assert wk[0]["ad_rise"] >= wk[-1]["ad_rise"]          # dysreflexia risk falls
    assert curve["summary"]["capacity_gain_pct"] > 0


def test_trained_day_is_safe():
    day = simulate_bladder_day(interval_h=4.0, trained=1.0)
    assert day["safe"] is True
    assert day["worst_ad_rise"] < 40.0


def test_protocols_target_sacral_contact():
    for p in PROTOCOLS.values():
        assert p.contact == 6  # S2 sacral contact on the 5-6-5 paddle
        assert p.rate_hz > 0 and p.pw_us > 0
