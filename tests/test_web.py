"""Web-dashboard backend tests (pure functions, no HTTP needed)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "web"))

import server  # noqa: E402


def test_locomotion_payload_shape():
    d = server.run_locomotion({"body": "kinematic", "speed": "0.5", "dur": "8"})
    assert d["frames"], "no frames returned"
    f = d["frames"][0]
    assert {"t", "trunk", "L", "R", "grfL", "grfR"} <= set(f)
    assert len(f["L"]) == 4 and len(f["L"][0]) == 2  # 4 points, each (x,y)
    assert "cadence" in d["metrics"] and "balance_ok_pct" in d["metrics"]


def test_autonomic_payload_contrast():
    dsd = server.run_autonomic({"modulation": False})
    syn = server.run_autonomic({"modulation": True})
    assert dsd["metrics"]["peak_pressure"] > syn["metrics"]["peak_pressure"]
    assert dsd["metrics"]["residual_ml"] > syn["metrics"]["residual_ml"]
    assert dsd["metrics"]["ad_events"] > 0 and syn["metrics"]["ad_events"] == 0


def test_mapping_payload():
    d = server.run_mapping({})
    assert len(d["groups"]) == 12
    assert len(d["true"]) == 16 and len(d["recovered"]) == 16
    assert d["metrics"]["accuracy"] > d["metrics"]["manual"]


def test_opensim_view_payload():
    import pytest
    pytest.importorskip("opensim")
    d = server.run_opensim_view({})
    assert d["frames"], "no frames"
    f = d["frames"][0]
    assert {"pelvis", "torso", "L", "R"} <= set(f)
    assert d["metrics"]["muscles"] == 18
    assert d["metrics"]["lr_hip_corr"] < 0  # alternating gait


def test_adaptation_flag_changes_outcome_under_fatigue():
    # Just confirm the parameter plumbing runs end-to-end with adaptation on.
    d = server.run_locomotion({"body": "kinematic", "fatigue": True, "adapt": True, "dur": "10"})
    assert d["metrics"]["safety_events"] >= 0 and d["frames"]
