"""Tests for the two deep 'unique' ideas: recovery-optimization and cohort prior."""

from __future__ import annotations

from bso.cohort import warm_vs_cold
from bso.plasticity import PlasticityModel, function_first_course, recovery_first_course


def test_pairing_quality_peaks_at_optimal_timing():
    m = PlasticityModel(tau_opt_ms=20.0)
    assert m.pairing_quality(20.0) > m.pairing_quality(60.0)
    assert m.pairing_quality(20.0) > m.pairing_quality(-30.0)


def test_recovery_first_heals_more_than_function_first():
    ff, _ = function_first_course(n_sessions=30, tau_opt_ms=20.0)
    rf, best = recovery_first_course(n_sessions=30, tau_opt_ms=20.0)
    assert rf[-1] > ff[-1] * 2          # recovery-optimized heals much more (stim OFF)
    assert abs(best - 20.0) < 25        # it discovered a near-optimal timing


def test_cohort_warm_start_beats_cold_at_low_budget():
    budgets, cold, warm = warm_vs_cold(n_cohort=12)
    assert warm[0] > cold[0] + 0.2      # big free head-start from the prior
    assert warm[-1] >= cold[-1] - 0.05  # converge with enough probes
