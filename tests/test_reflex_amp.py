"""Reflex as amplifier — a stable weight-bearing window exists between too-weak
and clonus, where a small central drive yields full support.

Locks in IZAR invention #6 on the delayed load-reflex model.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bso.reflex_amp import CENTRAL, reflex_run, sweep


def test_a_stable_weight_bearing_window_exists():
    s = sweep()
    assert s["window"] is not None
    lo, hi = s["window"]
    assert 0.0 < lo <= hi < 1.5


def test_low_gain_is_insufficient():
    r = reflex_run(0.2)
    assert not r["weight_bearing"]
    assert r["stable"]            # weak but not oscillating


def test_high_gain_is_clonus():
    r = reflex_run(1.4)
    assert not r["stable"]        # oscillates = clonus


def test_reflex_amplifies_small_drive():
    """Inside the window, support far exceeds the bare central drive."""
    s = sweep()
    assert s["amplification"] > 2.0
    assert s["amplification"] * CENTRAL > 0.3


def test_determinism():
    assert reflex_run(0.85) == reflex_run(0.85)
