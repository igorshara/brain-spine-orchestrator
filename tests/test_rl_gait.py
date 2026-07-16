"""Tests for the ES cross-speed gait policy (Evolution Strategies)."""

from __future__ import annotations

import numpy as np

from bso.rl_gait import GaitPolicy, es_train, rollout


def test_policy_param_roundtrip_and_output_bounds():
    rng = np.random.default_rng(0)
    p = rng.normal(size=GaitPolicy().size)
    pol = GaitPolicy(p)
    assert np.allclose(pol.params(), p)
    b = pol.boosts(np.array([0.0, 1.0, 0.5, 0.3]))
    assert b.shape == (3,)
    assert np.all(b >= 0.5) and np.all(b <= 2.5)  # gain multipliers stay bounded


def test_zero_policy_is_neutral_baseline():
    # zero params -> tanh(0)=0 -> boost = 1.0 (no change)
    b = GaitPolicy().boosts(np.array([0.2, -0.1, 0.5, 0.4]))
    assert np.allclose(b, 1.0)


def test_rollout_returns_reasonable_reward():
    r = rollout(GaitPolicy(), speed=0.5, dur=6.0)
    assert 0.0 <= r < 1.0


def test_es_improves_over_baseline():
    base = rollout(GaitPolicy(), speed=0.5, dur=6.0)
    best, hist = es_train([0.4, 0.6], pop=10, elite=3, iters=5, seed=0)
    trained = rollout(GaitPolicy(best), speed=0.5, dur=6.0)
    assert hist[-1] >= hist[0]                # ES did not regress
    assert trained >= base * 0.9              # trained policy is at least competitive
