"""Demo: drive a VALIDATED OpenSim musculoskeletal model with our orchestrator.

Демо достовірності на реальній моделі. Наш CPG-оркестратор задає патерн суглобових
кутів; ми приписуємо його валідованій моделі OpenSim ``gait10dof18musc`` (18 м'язів
Хілла) і зчитуємо РЕАЛЬНІ довжини м'язово-сухожилкових одиниць + анатомічні позиції
сегментів. Це чесний апгрейд: «наш патерн → валідована модель → реальна біомеханіка».

Потрібні opensim + matplotlib + models/gait10dof18musc.osim.
Запуск:  python3 scenarios/opensim_gait.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401
import numpy as np

from bso.biomech.opensim_model import OpenSimGaitAnalyzer
from bso.decoder_stub import IntentEvent
from bso.runtime import build_system
from bso.schemas import Mode

KEYS = ("L_hip", "L_knee", "L_ankle", "R_hip", "R_knee", "R_ankle")


def main(render: bool = True) -> None:
    rec = build_system([IntentEvent(0.0, Mode.STAND),
                        IntentEvent(1.0, Mode.WALK, speed=0.6)]).run(8.0)
    idx = list(range(1200, len(rec.pose), 8))
    frames = [{k: rec.pose[i][k] for k in KEYS} for i in idx]

    an = OpenSimGaitAnalyzer()
    res = an.analyze(frames)
    ml = res["muscle_lengths"]

    print("=== OpenSim validated model (gait10dof18musc, 18 Hill muscles) ===")
    print("  driven by our orchestrator's gait pattern (prescribed kinematics)")
    print(f"  {'muscle':14s} {'length range (m)':>20} {'excursion (mm)':>15}")
    for mu in ("iliopsoas_r", "glut_max_r", "hamstrings_r", "vasti_r", "gastroc_r", "tib_ant_r"):
        L = np.array(ml[mu])
        print(f"  {mu:14s} {L.min():8.3f} .. {L.max():.3f}      {(L.max() - L.min()) * 1000:8.1f}")
    print("  -> physiologically plausible muscle excursions on a validated model "
          "(not hand-authored).")

    if render:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(1, 2, figsize=(13, 6))
        fig.suptitle("Our orchestrator's gait on a validated OpenSim model "
                     "(gait10dof18musc)\n[anatomical proportions & real muscle lengths · "
                     "ILLUSTRATIVE drive]", fontsize=11)
        # left: anatomically-proportioned sagittal figure (mid-cycle)
        figpose = res["figures"][len(frames) // 2]
        ax[0].plot([figpose["pelvis"][0], figpose["torso"][0]],
                   [figpose["pelvis"][1], figpose["torso"][1]], "o-", color="0.3", lw=4)
        for side, col in (("l", "tab:blue"), ("r", "tab:red")):
            xs = [p[0] for p in figpose[side]]
            ys = [p[1] for p in figpose[side]]
            ax[0].plot(xs, ys, "o-", color=col, lw=3, label=side.upper())
        ax[0].axhline(0, color="0.7", lw=1)
        ax[0].set_aspect("equal")
        ax[0].set_title("Real segment geometry (femur/tibia/calcn/toes)")
        ax[0].legend()
        ax[0].set_xlabel("anterior (m)")
        ax[0].set_ylabel("vertical (m)")
        # right: muscle length excursions over the cycle
        t = np.arange(len(frames)) * 0.04
        for mu in ("iliopsoas_r", "hamstrings_r", "vasti_r", "gastroc_r", "tib_ant_r"):
            ax[1].plot(t, np.array(ml[mu]) * 1000, label=mu, lw=1.4)
        ax[1].set_xlabel("time (s)")
        ax[1].set_ylabel("muscle-tendon length (mm)")
        ax[1].set_title("Real muscle-tendon excursions during gait")
        ax[1].legend(fontsize=8)
        ax[1].grid(alpha=0.3)
        out = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "opensim_gait.png")
        fig.tight_layout(rect=(0, 0, 1, 0.94))
        fig.savefig(out, dpi=110)
        plt.close(fig)
        print("saved:", out)


if __name__ == "__main__":
    main()
