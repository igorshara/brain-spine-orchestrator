"""Predictive AD-guardian tests — it must prevent AD where reactive care fails."""

from __future__ import annotations

from bso.ad_guardian import ADGuardian, simulate


def test_guardian_forecasts_rising_pressure():
    g = ADGuardian(horizon_s=40, warn_pressure_cmH2O=22)
    for t in range(6):
        info = g.observe(t * 1.0, 5.0 + t * 2.0)  # pressure rising 2/s
    assert info["slope"] > 1.0
    assert info["forecast"] > 5.0 + 5 * 2.0  # forecast extrapolates upward


def test_predictive_prevents_ad_vs_none_and_reactive():
    _, none = simulate("none")
    _, react = simulate("reactive")
    _, pred = simulate("predictive")
    assert none["ad_events"] > 50            # unmanaged dyssynergia floods AD
    assert pred["ad_events"] == 0            # predictive prevents it entirely
    assert pred["ad_events"] < react["ad_events"]  # better than reactive
    assert pred["peak_pressure"] < none["peak_pressure"]


def test_guardian_adapts_to_fill_rate():
    _, slow = simulate("predictive", fill_ml_per_s=1.0)
    _, fast = simulate("predictive", fill_ml_per_s=3.0)
    # faster filling -> the guardian warns at least as early (smaller/equal time)
    assert fast["first_warning_s"] is not None and slow["first_warning_s"] is not None
    assert fast["first_warning_s"] <= slow["first_warning_s"] + 1e-6
    assert fast["ad_events"] == 0 and slow["ad_events"] == 0
