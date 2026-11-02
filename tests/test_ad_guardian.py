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
    assert none["ad_episodes"] > 5           # unmanaged dyssynergia repeats episodes
    assert pred["ad_episodes"] == 0          # predictive stays below the limit
    assert pred["ad_episodes"] < react["ad_episodes"]  # better than reactive
    assert pred["peak_pressure"] < none["peak_pressure"]


def test_guardian_adapts_to_fill_rate():
    _, slow = simulate("predictive", fill_ml_per_s=1.0)
    _, fast = simulate("predictive", fill_ml_per_s=3.0)
    # faster filling -> the guardian warns at least as early (smaller/equal time)
    assert fast["first_warning_s"] is not None and slow["first_warning_s"] is not None
    assert fast["first_warning_s"] <= slow["first_warning_s"] + 1e-6
    assert fast["ad_episodes"] == 0 and slow["ad_episodes"] == 0


def test_metrics_report_the_bladder_references_the_charts_draw():
    _, m = simulate("none")
    assert m["ad_trigger_pressure"] == 60.0
    assert m["start_volume"] > 0


def test_metrics_report_the_baseline_the_chart_draws():
    _, metrics = simulate("none")
    assert metrics["baseline_bp"] == 110.0


def test_episode_metrics_converge_across_time_steps():
    for policy in ("none", "reactive", "predictive"):
        runs = [simulate(policy, dt=dt)[1] for dt in (0.25, 0.1, 0.05)]
        assert len({m["ad_episodes"] for m in runs}) == 1, policy
        seconds = [m["ad_seconds_above_limit"] for m in runs]
        assert max(seconds) - min(seconds) <= 1.0, policy
        peaks = [m["peak_bp_rise"] for m in runs]
        assert max(peaks) - min(peaks) <= 1.0, policy
