"""OpenSim validated-model integration tests. Skipped if opensim/model absent."""

from __future__ import annotations

import os

import numpy as np
import pytest

pytest.importorskip("opensim")

from bso.biomech.opensim_model import DEFAULT_MODEL, OpenSimGaitAnalyzer  # noqa: E402
from bso.decoder_stub import IntentEvent  # noqa: E402
from bso.runtime import build_system  # noqa: E402
from bso.schemas import Mode  # noqa: E402

if not os.path.exists(os.path.abspath(DEFAULT_MODEL)):
    pytest.skip("gait10dof18musc.osim not present", allow_module_level=True)

KEYS = ("L_hip", "L_knee", "L_ankle", "R_hip", "R_knee", "R_ankle")


def _frames():
    rec = build_system([IntentEvent(0.0, Mode.STAND),
                        IntentEvent(1.0, Mode.WALK, speed=0.6)]).run(6.0)
    idx = list(range(800, len(rec.pose), 12))
    return [{k: rec.pose[i][k] for k in KEYS} for i in idx]


def test_model_loads_with_expected_muscles():
    an = OpenSimGaitAnalyzer()
    assert len(an.muscle_names) == 18
    assert "iliopsoas_r" in an.muscle_names and "gastroc_l" in an.muscle_names


def test_muscle_lengths_change_with_gait():
    an = OpenSimGaitAnalyzer()
    res = an.analyze(_frames())
    for mu in ("iliopsoas_r", "vasti_r", "gastroc_r"):
        L = np.array(res["muscle_lengths"][mu])
        assert L.max() - L.min() > 0.003  # at least a few mm of excursion
        assert np.all(L > 0.05) and np.all(L < 1.0)  # plausible absolute length


def test_anatomical_figure_descends():
    an = OpenSimGaitAnalyzer()
    res = an.analyze(_frames())
    f = res["figures"][len(res["figures"]) // 2]
    # leg points should descend from pelvis toward the foot
    ys = [p[1] for p in f["r"]]
    assert ys[0] > ys[-1]


def test_group_to_muscle_map_is_anatomical():
    an = OpenSimGaitAnalyzer()
    m = an.group_to_muscles()
    assert "iliopsoas_l" in m["L_hip_flex"]
    assert "gastroc_r" in m["R_ankle_plantar"]


def test_muscle_driven_forward_dynamics_produces_alternating_gait():
    from bso.biomech.opensim_model import run_muscle_driven
    rec = build_system([IntentEvent(0.0, Mode.STAND),
                        IntentEvent(1.0, Mode.WALK, speed=0.6)]).run(5.0)
    res = run_muscle_driven(rec.activations, rec.t, t_start=1.0, duration=2.5)
    hipR = np.array(res["R_hip"][15:])
    hipL = np.array(res["L_hip"][15:])
    # legs actually moved under muscle action, and alternate left/right
    assert hipR.max() - hipR.min() > 10
    assert np.corrcoef(hipR, hipL)[0, 1] < -0.2
