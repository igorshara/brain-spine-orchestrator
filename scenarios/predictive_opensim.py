"""Shadow Step on the OpenSim model: an honest check of the mechanism.

Activations from the closed loop on the Hill twin (reactive vs predictive) drive
gait10dof18musc (18 Hill muscles) in forward dynamics with joint stops and no ground
contact. Result as of 2026-11-02: no clearance gain. The earlier 4.56 -> 4.82 cm came
from a run without joint stops, where the knee bent 40 degrees backwards.

Запуск:  python3 scenarios/predictive_opensim.py   (потрібен OpenSim 4.x)
Усе ILLUSTRATIVE — дослідницька симуляція, не клінічні числа.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bso.biomech.kinematic import KinematicModel  # noqa: E402
from bso.decoder_stub import IntentEvent  # noqa: E402
from bso.runtime import build_system  # noqa: E402
from bso.schemas import Mode  # noqa: E402

T_START, DURATION = 4.0, 3.0
LOW_CLEAR_M = 0.03   # toe below this (m) on the validated model = poor clearance


def _activations(mode: str):
    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]
    s = build_system(sched, dt=0.005, model=KinematicModel(use_muscles=True))
    s.feedback.mode = mode
    s.feedback.lead_ms, s.feedback.pred_gain, s.feedback.pred_tail_gain = 100.0, 1.5, 0.5
    rec = s.run(T_START + DURATION + 1.0)
    return rec.activations, rec.t


def _opensim_metrics(mode: str) -> dict:
    from bso.biomech.opensim_model import run_muscle_driven
    acts, t = _activations(mode)
    res = run_muscle_driven(acts, t, t_start=T_START, duration=DURATION)
    toes = [min(f["l"][-1][1], f["r"][-1][1]) for f in res["figures"]]
    mean_clear = sum(toes) / len(toes)
    low = sum(1 for y in toes if y < LOW_CLEAR_M)
    raised = [max(f["l"][-1][1], f["r"][-1][1]) for f in res["figures"]]
    return {"mean_clear_cm": round(100.0 * mean_clear, 2),
            "mean_raised_toe_cm": round(100.0 * sum(raised) / len(raised), 2),
            "low_clear_frames": low, "frames": len(toes)}


def main():
    print(f"Shadow Step on the OpenSim model (18 Hill muscles). "
          f"Window {T_START:.0f}-{T_START+DURATION:.0f}s. ILLUSTRATIVE.\n")
    print(f"{'arm':<14}{'mean_clear_cm':>16}{'raised_toe_cm':>16}{'low_clear_frames':>20}")
    print("-" * 66)
    res = {}
    for mode in ("reactive", "predictive"):
        m = _opensim_metrics(mode)
        res[mode] = m
        print(f"{mode:<14}{m['mean_clear_cm']:>16}{m['mean_raised_toe_cm']:>16}{m['low_clear_frames']:>20}")
    print("-" * 66)
    r, p = res["reactive"], res["predictive"]
    d = round(p["mean_raised_toe_cm"] - r["mean_raised_toe_cm"], 2)
    print(f"\nraised-foot toe height, reactive to predictive: "
          f"{r['mean_raised_toe_cm']} -> {p['mean_raised_toe_cm']} cm ({d:+} cm).")
    if d > 0:
        print("The shadow step lifts the foot higher on this model.")
    else:
        print("No gain on this model. The gain appears only on the simplified twin.")


if __name__ == "__main__":
    main()
