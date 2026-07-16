"""Shadow Step validated on the OpenSim model (skips if OpenSim is absent).

The closed-loop activations from the Hill twin (reactive vs predictive) are run
through the validated gait10dof18musc model; the shadow step must lift the foot
no lower than reactive on real anatomy — the mechanism beyond the simple twin.
"""

from __future__ import annotations

import os
import sys

import pytest

pytest.importorskip("opensim")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scenarios.predictive_opensim import _opensim_metrics  # noqa: E402


def test_shadow_step_holds_on_validated_opensim_model():
    reactive = _opensim_metrics("reactive")
    predictive = _opensim_metrics("predictive")
    assert predictive["mean_clear_cm"] >= reactive["mean_clear_cm"], (
        f"predictive should not lift lower on real anatomy: "
        f"pred={predictive['mean_clear_cm']} react={reactive['mean_clear_cm']}")
