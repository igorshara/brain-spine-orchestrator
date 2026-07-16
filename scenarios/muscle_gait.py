"""Demo: Hill-type muscle dynamics vs instantaneous activation→movement.

Демо м'язової фізіології. Той самий CPG, але тіло з Hill-моделлю м'язів (динаміка
активації + сила-довжина/швидкість) проти прямого мапінгу. Показуємо, як динаміка
активації ЗГЛАДЖУЄ й демпфує рух (м'яз не встигає за швидкими командами), що
фізіологічно правдивіше. Усе ILLUSTRATIVE.

Потрібен matplotlib. Запуск:  python3 scenarios/muscle_gait.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401

from bso.biomech.kinematic import KinematicModel
from bso.decoder_stub import IntentEvent
from bso.runtime import build_system
from bso.schemas import Mode


def main(render: bool = True) -> None:
    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]
    recs = {
        "direct activation": build_system(sched, model=KinematicModel()).run(10.0),
        "Hill muscles": build_system(sched, model=KinematicModel(use_muscles=True)).run(10.0),
    }

    print("=== MUSCLE DYNAMICS vs direct activation ===")
    for label, rec in recs.items():
        lk = [p["L_knee"] for p in rec.pose[1000:]]
        fy = [p["L_foot_y"] for p in rec.pose[1000:]]
        print(f"  {label:18s} knee ROM={min(lk):.0f}..{max(lk):.0f} deg  "
              f"foot clearance={max(fy) - min(fy):.3f} m")
    print("  -> muscle activation dynamics + force-length damp the motion "
          "(physiologically truer than instantaneous activation).")

    if render:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
        fig.suptitle("Hill-type muscle dynamics vs direct activation\n"
                     "[RESEARCH SIMULATION — ILLUSTRATIVE]", fontsize=12)
        for label, rec in recs.items():
            ax[0].plot(rec.t, [p["L_knee"] for p in rec.pose], label=label, lw=1.3)
        ax[0].set_ylabel("L knee angle (deg)")
        ax[0].set_title("Knee kinematics — muscles smooth/damp the trajectory")
        ax[0].legend()
        ax[0].grid(alpha=0.3)

        # excitation (commanded) vs achieved muscle activation for one muscle
        rec = recs["Hill muscles"]
        exc = [a.get("L_knee_flex", 0.0) for a in rec.activations]
        ax[1].plot(rec.t, exc, label="commanded excitation (L_knee_flex)", lw=1.0)
        ax[1].set_ylabel("activation")
        ax[1].set_xlabel("time (s)")
        ax[1].set_title("Commanded excitation — muscle activation lags it (rise≠fall)")
        ax[1].legend()
        ax[1].grid(alpha=0.3)

        out = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "muscle_gait.png")
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        fig.savefig(out, dpi=110)
        plt.close(fig)
        print("saved:", out)


if __name__ == "__main__":
    main()
