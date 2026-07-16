"""Demo: MUSCLE-DRIVEN forward dynamics on the validated OpenSim model.

Демо м'язово-керованої прямої динаміки. Активації від нашого CPG-оркестратора
стають збудженнями 18 м'язів Хілла валідованої моделі OpenSim; з підтримкою таза
(body-weight support, як реабілітаційна рама) ноги РУХАЮТЬСЯ САМИМИ М'ЯЗАМИ — це
справжня forward-динаміка, не приписані кути. Показуємо, що патерн стимуляції
породжує координовану чергувальну ходу через реальні м'язи. Усе ILLUSTRATIVE.

Потрібні opensim + matplotlib + models/gait10dof18musc.osim.
Запуск:  python3 scenarios/opensim_muscle_driven.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401
import numpy as np

from bso.biomech.opensim_model import run_muscle_driven
from bso.decoder_stub import IntentEvent
from bso.runtime import build_system
from bso.schemas import Mode


def main(render: bool = True) -> None:
    rec = build_system([IntentEvent(0.0, Mode.STAND),
                        IntentEvent(1.0, Mode.WALK, speed=0.6)]).run(5.0)
    res = run_muscle_driven(rec.activations, rec.t, t_start=1.0, duration=3.0)

    hipR = np.array(res["R_hip"][15:])
    hipL = np.array(res["L_hip"][15:])
    corr = float(np.corrcoef(hipR, hipL)[0, 1])
    print("=== MUSCLE-DRIVEN forward dynamics (OpenSim gait10dof18musc, 18 Hill muscles) ===")
    print("  legs moved by MUSCLE FORCES from our CPG excitations (body-weight supported)")
    print(f"  hip ROM: R {hipR.min():.0f}..{hipR.max():.0f} deg, "
          f"L {hipL.min():.0f}..{hipL.max():.0f} deg")
    print(f"  L/R hip correlation = {corr:.2f} (negative = alternating gait)")
    print("  -> the orchestrator's stimulation pattern produces coordinated gait via "
          "real muscle forward dynamics, not prescribed angles.")

    if render:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(1, 2, figsize=(13, 5.5))
        fig.suptitle("Muscle-driven forward dynamics on a validated OpenSim model\n"
                     "[legs moved by 18 Hill muscles under our excitations · "
                     "body-weight supported · ILLUSTRATIVE]", fontsize=11)
        figp = res["figures"][len(res["figures"]) // 2]
        ax[0].plot([figp["pelvis"][0], figp["torso"][0]],
                   [figp["pelvis"][1], figp["torso"][1]], "o-", color="0.3", lw=4)
        for side, col in (("l", "tab:blue"), ("r", "tab:red")):
            ax[0].plot([p[0] for p in figp[side]], [p[1] for p in figp[side]],
                       "o-", color=col, lw=3, label=side.upper())
        ax[0].axhline(0, color="0.7", lw=1)
        ax[0].set_aspect("equal")
        ax[0].set_title("Real anatomy, moved by muscle forces")
        ax[0].legend()
        ax[0].set_xlabel("anterior (m)")
        ax[0].set_ylabel("vertical (m)")
        t = res["t"]
        ax[1].plot(t, res["R_hip"], label="hip R", color="tab:red")
        ax[1].plot(t, res["L_hip"], label="hip L", color="tab:blue")
        ax[1].plot(t, res["R_knee"], label="knee R", color="tab:orange", lw=1, ls="--")
        ax[1].set_xlabel("time (s)")
        ax[1].set_ylabel("joint angle (deg)")
        ax[1].set_title(f"Muscle-driven joint trajectories (L/R hip corr {corr:.2f})")
        ax[1].legend(fontsize=8)
        ax[1].grid(alpha=0.3)
        out = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "opensim_muscle_driven.png")
        fig.tight_layout(rect=(0, 0, 1, 0.93))
        fig.savefig(out, dpi=110)
        plt.close(fig)
        print("saved:", out)


if __name__ == "__main__":
    main()
