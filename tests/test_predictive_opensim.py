"""Shadow Step on the OpenSim model (skips if OpenSim is absent).

With joint stops the mechanism shows no clearance gain on this model, so the public
copy must not claim one. If this test fails, the result changed: update that copy.
"""

from __future__ import annotations

import os
import sys

import pytest

pytest.importorskip("opensim")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scenarios.predictive_opensim import _opensim_metrics  # noqa: E402


def test_shadow_step_shows_no_clearance_gain_on_opensim_model():
    reactive = _opensim_metrics("reactive")
    predictive = _opensim_metrics("predictive")
    assert predictive["mean_raised_toe_cm"] <= reactive["mean_raised_toe_cm"]


def test_public_copy_does_not_claim_the_old_opensim_gain():
    page = os.path.join(os.path.dirname(__file__), "..", "web", "index.html")
    with open(page, encoding="utf-8") as f:
        assert "4.56 → 4.82" not in f.read()
