"""GP Bayesian-optimization tests — implementation correctness on benchmarks.

We validate the optimizer on a textbook needle-in-haystack so its later use for
autonomous stimulation mapping rests on a verified method (not a hand-waved one).
"""

from __future__ import annotations

import numpy as np

from bso.bopt import GaussianProcess, bayes_optimize, queries_to_target, random_search


def test_gp_interpolates_known_points():
    gp = GaussianProcess(length_scale=0.3, noise=1e-6)
    X = np.array([[0.0], [0.5], [1.0]])
    y = np.array([0.0, 1.0, 0.0])
    gp.fit(X, y)
    mu, var = gp.predict(X)
    assert np.allclose(mu, y, atol=1e-2)
    assert np.all(var >= 0)


def test_bo_beats_random_on_needle_benchmark():
    grid = np.linspace(0, 1, 40)
    cands = np.array([[x, y] for x in grid for y in grid])

    def f(p):
        return float(np.exp(-((p[0] - 0.7) ** 2 + (p[1] - 0.3) ** 2) / (2 * 0.05 ** 2)))

    gopt = max(f(x) for x in cands)
    bo, rs = [], []
    for s in range(8):
        b = bayes_optimize(f, cands, n_init=6, n_iter=22, seed=s)
        r = random_search(f, cands, 28, seed=s)
        bo.append(b["history"][20] / gopt)
        rs.append(r["history"][20] / gopt)
    # On a hard needle, GP-BO should dominate random by a wide margin.
    assert np.mean(bo) > 0.8
    assert np.mean(bo) > np.mean(rs) + 0.3


def test_bo_history_is_monotonic():
    cands = np.array([[x] for x in np.linspace(0, 1, 50)])

    def f(p):
        return float(-(p[0] - 0.62) ** 2)

    b = bayes_optimize(f, cands, n_init=4, n_iter=15, seed=0)
    h = b["history"]
    assert all(h[i + 1] >= h[i] - 1e-9 for i in range(len(h) - 1))
    assert queries_to_target(h, max(h)) <= len(h)
