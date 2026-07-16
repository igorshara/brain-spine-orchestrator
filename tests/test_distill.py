"""Policy-distillation tests (numpy MLP behavioral cloning)."""

from __future__ import annotations

import numpy as np

from bso.distill import MLPRegressor, r2


def test_mlp_learns_a_smooth_function():
    rng = np.random.default_rng(0)
    X = rng.uniform(-1, 1, (200, 3))
    y = np.column_stack([np.sin(X[:, 0]) + 0.5 * X[:, 1],
                         (X[:, 2] ** 2 - X[:, 0])])
    m = MLPRegressor(3, 2, n_hidden=24)
    m.fit(X, y, epochs=3000, lr=5e-3)
    assert r2(y, m.forward(X)) > 0.9


def test_generalizes_to_holdout():
    rng = np.random.default_rng(1)
    X = rng.uniform(-1, 1, (300, 4))
    y = np.tanh(X @ rng.normal(size=(4, 3)))
    tr, va = X[:240], X[240:]
    ytr, yva = y[:240], y[240:]
    m = MLPRegressor(4, 3, n_hidden=20).fit(tr, ytr, epochs=3000)
    assert r2(yva, m.forward(va)) > 0.85


def test_save_roundtrip(tmp_path):
    m = MLPRegressor(3, 2, n_hidden=8)
    p = str(tmp_path / "pol.json")
    m.save(p)
    import json
    d = json.load(open(p))
    assert set(d) == {"W1", "b1", "W2", "b2"}


def test_inference_is_fast():
    import time
    m = MLPRegressor(14, 18, n_hidden=24)
    x = np.zeros((1, 14))
    t0 = time.perf_counter()
    for _ in range(1000):
        m.forward(x)
    per_call_us = (time.perf_counter() - t0) / 1000 * 1e6
    assert per_call_us < 200  # comfortably real-time
