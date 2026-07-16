"""Sensory closed loop — proprioception (rate of sway) is what keeps standing.

Locks in IZAR invention #5: on an inverted-pendulum standing model, only the
proprioceptive controller (position + velocity) stays upright under perturbation;
position-only and no-sensation both fall. Physiologically: loss of proprioception
= sensory ataxia.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bso.balance_sensory import balance_run, compare


def test_proprioception_stays_upright():
    assert balance_run("proprioceptive")["upright"] is True


def test_position_only_and_no_sensation_fall():
    assert balance_run("reactive")["fell"] is True
    assert balance_run("off")["fell"] is True


def test_proprioception_sways_least():
    r = compare()["modes"]
    assert r["proprioceptive"]["max_tilt_deg"] < r["reactive"]["max_tilt_deg"]
    assert r["reactive"]["max_tilt_deg"] < r["off"]["max_tilt_deg"]


def test_determinism():
    assert balance_run("proprioceptive") == balance_run("proprioceptive")
