"""Dual lock — EES priming + selective periphery beats single-channel EES.

Locks in IZAR invention #4: for the same net joint force, the dual lock reaches
target with less charge and zero antagonist spillover, and its advantage grows
with current spread (coupling) — the very problem single-channel EES suffers.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bso.dual_lock import compare, dual_lock, single_ees


def test_dual_lock_uses_less_charge_at_realistic_coupling():
    r = compare(target_net=0.5, coupling=0.3)
    assert r["dual"]["charge"] < r["single"]["charge"]
    assert r["charge_saving_pct"] > 10.0


def test_dual_lock_removes_antagonist_spillover():
    r = compare(target_net=0.5, coupling=0.3)
    assert r["dual"]["spillover"] == 0.0
    assert r["single"]["spillover"] > 0.0


def test_advantage_grows_with_current_spread():
    """The charge saving increases monotonically with coupling."""
    savings = [compare(0.5, c)["charge_saving_pct"] for c in (0.0, 0.1, 0.2, 0.3, 0.4)]
    assert all(savings[i] <= savings[i + 1] for i in range(len(savings) - 1))
    assert savings[-1] > savings[0]


def test_both_strategies_meet_the_target():
    s = single_ees(0.5, 0.3)
    d = dual_lock(0.5)
    assert abs(s["net"] - 0.5) < 1e-2
    assert abs(d["net"] - 0.5) < 1e-2
