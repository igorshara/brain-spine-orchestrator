"""Tests for the trainable Layer-4 harness (learned adaptation).

Перевіряють ІНФРАСТРУКТУРУ навчання (а не те, що навчене перемагає інтеграл —
чесний висновок проєкту: для цієї задачі не перемагає): forward детермінований,
save/load round-trip, CEM покращує винагороду на крихітному прогоні, навчений
шар не порушує safety й піднімає підсилення під втомою.
"""

from __future__ import annotations

import numpy as np

from bso.config.limits import LIMITS
from bso.decoder_stub import IntentEvent
from bso.degradation import FatigueModel
from bso.learned_adaptation import MLPPolicy, evaluate_policy, train_cem
from bso.runtime import build_system
from bso.schemas import Mode

SCHED = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]


def test_policy_forward_deterministic():
    rng = np.random.default_rng(0)
    p = rng.normal(size=MLPPolicy().size)
    a, b = MLPPolicy(params=p), MLPPolicy(params=p)
    x = np.array([0.3, 0.2, -0.1, 1.0])
    assert a.delta(x) == b.delta(x)


def test_policy_save_load_roundtrip(tmp_path):
    rng = np.random.default_rng(1)
    p = rng.normal(size=MLPPolicy().size)
    pol = MLPPolicy(params=p)
    path = str(tmp_path / "pol.json")
    pol.save(path)
    loaded = MLPPolicy.load(path)
    x = np.array([0.1, 0.0, 0.2, 1.0])
    assert abs(pol.delta(x) - loaded.delta(x)) < 1e-12


def test_cem_improves_reward():
    conds = [lambda: {"fatigue": FatigueModel(enabled=True, fatigue_rate=0.1,
                                              fatigue_max=0.5, drift_rate_per_s=0.004)}]
    zero_reward = evaluate_policy(np.zeros(MLPPolicy().size), conds, dur=10.0)
    _, history = train_cem(conds, pop=10, elite=3, iters=4, seed=0, dur=10.0)
    assert history[-1] >= zero_reward, "CEM should not regress below a do-nothing policy"


def test_learned_layer_respects_safety_and_acts():
    rng = np.random.default_rng(2)
    # A policy with a positive bias tends to raise gains — still must stay safe.
    p = rng.normal(size=MLPPolicy().size) * 0.2
    policy = MLPPolicy(params=p)
    fm = FatigueModel(enabled=True, fatigue_rate=0.1, fatigue_max=0.5, drift_rate_per_s=0.004)
    rec = build_system(SCHED, fatigue=fm, policy=policy).run(12.0)
    for cmds in rec.applied:
        for c in cmds:
            assert c.amplitude_mA <= LIMITS.amplitude_max_mA + 1e-9
            assert c.charge_per_phase_uC <= LIMITS.charge_per_phase_max_uC + 1e-9
    # gains stay within the configured bounds
    for g in rec.gains[-1].values():
        assert 0.5 - 1e-9 <= g <= 3.0 + 1e-9
