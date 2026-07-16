"""Cohort foundation model — cold-start personalisation.

Wraps the cohort meta-learned prior (`cohort.py`) into a clean "foundation model"
API: a prior learned from the WHOLE cohort suggests a starting stimulation
configuration for a new patient from query ZERO — instead of hours of blind
titration. The unfair advantage is a cohort no one else has (a large SCI /
military cohort). Every new patient also makes the prior better.

Illustrative research simulation — not a medical device; numbers are illustrative.
"""
from __future__ import annotations

import numpy as np

from .cohort import build_cohort, cohort_prior, map_with_budget, warm_vs_cold
from .mapping import GROUPS, ElectrodeArray, best_contact_per_group


def lift_summary(n_cohort: int = 16, jitter: float = 0.7, seed: int = 0) -> dict:
    """How much the cohort prior lifts mapping accuracy at each probe budget —
    especially at ZERO probes (pure cold-start), the headline number."""
    budgets, cold, warm = warm_vs_cold(n_cohort=n_cohort, jitter=jitter, seed=seed)
    z = budgets.index(0)
    return {
        "budgets": list(budgets),
        "cold": [round(float(x), 3) for x in cold],
        "warm": [round(float(x), 3) for x in warm],
        "cold_zero_pct": round(float(cold[z]) * 100),
        "warm_zero_pct": round(float(warm[z]) * 100),
        "n_cohort": n_cohort,
    }


def cold_start_config(n_cohort: int = 16, jitter: float = 0.7, seed: int = 0) -> dict:
    """Suggest a per-muscle-group starting contact from the cohort prior alone
    (zero patient probes) — the config a clinician would begin from on day one."""
    cohort = build_cohort(n_cohort, jitter=jitter, seed=seed)
    prior = cohort_prior(cohort)
    best = best_contact_per_group(prior)
    return {
        "n_cohort": n_cohort,
        "suggested": [{"group": g, "contact": int(best[g]) + 1} for g in GROUPS],
        "note": "Cold-start from cohort prior (0 patient probes); clinician refines.",
    }


def summary(n_cohort: int = 16) -> dict:
    lift = lift_summary(n_cohort=n_cohort)
    cfg = cold_start_config(n_cohort=n_cohort)
    return {**lift, "suggested": cfg["suggested"]}
