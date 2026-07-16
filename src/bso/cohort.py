"""Cohort meta-learned mapping prior — every patient makes the next one faster.

Ідея 3 з vision (структурна монополія 1ТМО): сьогодні кожного пацієнта мапять з нуля.
Маючи когорту, мапу нового пацієнта можна ТЕПЛО СТАРТУВАТИ з усередненого пріору,
вивченого на попередніх — і доналаштувати кількома пробами замість десятків. Що
більша когорта, то менше проб треба новому. Синтетична когорта (ILLUSTRATIVE), але
механізм (трансфер/мета-навчання пріору) реальний.
"""

from __future__ import annotations

import numpy as np

from .mapping import GROUPS, ElectrodeArray, best_contact_per_group


def build_cohort(n: int, jitter: float = 0.7, seed: int = 0) -> list[ElectrodeArray]:
    return [ElectrodeArray(seed=1000 + seed * 100 + k, jitter=jitter) for k in range(n)]


def cohort_prior(cohort: list[ElectrodeArray]) -> np.ndarray:
    """Mean recruitment map across the cohort — the warm-start prior."""
    return np.mean([a.W for a in cohort], axis=0)


def map_with_budget(patient: ElectrodeArray, n_probes: int, prior=None, seed: int = 0):
    """Estimate the patient's map probing only `n_probes` contacts (one ramp each),
    optionally starting from a cohort `prior`. Returns best-contact accuracy."""
    rng = np.random.default_rng(seed)
    W_hat = (prior.copy() if prior is not None else np.zeros_like(patient.W))
    order = rng.permutation(patient.n_contacts)[:n_probes]
    for c in order:
        W_hat[c] = patient.stimulate(c, 8.0, rng)  # measured row replaces the prior
    truth = best_contact_per_group(patient.W)
    est = best_contact_per_group(W_hat)
    return sum(truth[g] == est[g] for g in GROUPS) / len(GROUPS)


def warm_vs_cold(n_cohort: int = 12, jitter: float = 0.7, seed: int = 0):
    """Compare cold-start (no prior) vs warm-start (cohort prior) mapping accuracy
    across probe budgets, on a held-out patient not in the cohort."""
    cohort = build_cohort(n_cohort, jitter=jitter, seed=seed)
    prior = cohort_prior(cohort)
    heldout = ElectrodeArray(seed=999_999, jitter=jitter)
    budgets = list(range(0, 17, 2))
    cold = [np.mean([map_with_budget(heldout, b, None, seed=s) for s in range(5)])
            for b in budgets]
    warm = [np.mean([map_with_budget(heldout, b, prior, seed=s) for s in range(5)])
            for b in budgets]
    return budgets, cold, warm
