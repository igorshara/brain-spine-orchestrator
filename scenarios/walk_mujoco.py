"""Demo: the SAME CPG orchestrator driving a DYNAMIC MuJoCo physics body.

Демо динамічної фізики: той самий диригент (CPG) і той самий safety-шар, але тіло —
планарний двоногий у MuJoCo з підвісом часткового розвантаження ваги. Стимуляція
переводиться у референсні кути, PD-контролери дають моменти, MuJoCo рахує
динаміку й реальні КОНТАКТНІ сили. Це апгрейд достовірності: GRF та удар стопи
фізичні, а не задані кінематично. Усе ILLUSTRATIVE.

Потрібен пакет mujoco (pip install mujoco). Запуск:  python3 scenarios/walk_mujoco.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401
import numpy as np

from bso.biomech.mujoco_model import MuJoCoModel
from bso.decoder_stub import IntentEvent
from bso.runtime import build_system
from bso.schemas import Mode


def main(render: bool = True) -> None:
    schedule = [IntentEvent(0.0, Mode.STAND), IntentEvent(2.0, Mode.WALK, speed=0.45)]
    rec = build_system(schedule, model=MuJoCoModel()).run(12.0)

    n0 = int(4 / 0.005)
    pz = [p["pelvis_z"] for p in rec.pose[n0:]]
    trunk = [abs(p["trunk"]) for p in rec.pose[n0:]]
    grfL = np.array([f.grf["L"] for f in rec.frames[n0:] if f])
    grfR = np.array([f.grf["R"] for f in rec.frames[n0:] if f])
    gs = [g for g in rec.gait_state if g is not None]

    print("=== WALK (MuJoCo dynamic physics) ===")
    print(f"upright: pelvis height mean={np.mean(pz):.2f} m, "
          f"trunk lean p95={np.percentile(trunk, 95):.1f} deg")
    print(f"ground reaction force L: median={np.median(grfL):.0f} N, peak={grfL.max():.0f} N "
          f"(body weight ~490 N)")
    print(f"stance alternation L/R correlation={np.corrcoef(grfL, grfR)[0, 1]:.2f} (−1 = perfect)")
    print(f"balance ok ratio={sum(g.balance_ok for g in gs) / len(gs):.2f}, "
          f"safety events={len(rec.safety_events)}")

    if render:
        from bso.viz.dashboard import save_animation, save_summary

        out = os.path.abspath(_bootstrap.OUTPUT_DIR)
        print("saved:", save_summary(rec, os.path.join(out, "walk_mujoco_summary.png"),
                                      title="WALK — MuJoCo dynamic physics"))
        print("saved:", save_animation(rec, os.path.join(out, "walk_mujoco.gif"),
                                        stride=8, title="WALK (MuJoCo)"))


if __name__ == "__main__":
    main()
