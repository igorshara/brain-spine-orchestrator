"""Demo: active closed-loop balance recovery on MuJoCo physics.

Демо активного відновлення рівноваги. Під час ходи на динамічному тілі ми даємо
зовнішній поштовх у тулуб. Feedback (Шар 3) бачить нахил, знижує balance_ok і
підсилює trunk_stab; активний trunk-контролер дає коригувальний момент і повертає
тулуб у вертикаль. Порівнюємо ACTIVE (закритий контур) проти PASSIVE (лише
пасивний харнес). Усе ILLUSTRATIVE.

Потрібні mujoco + matplotlib. Запуск:  python3 scenarios/balance_recovery.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401
import numpy as np

from bso.biomech.mujoco_model import MuJoCoModel
from bso.decoder_stub import IntentEvent
from bso.runtime import build_system
from bso.schemas import Mode

PUSH_T = 6.0
PUSH = 6.0  # rad/s impulse into pelvis pitch


def _run(active: bool):
    model = MuJoCoModel()
    model.active_balance = active
    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(2.0, Mode.WALK, speed=0.45)]
    sys_ = build_system(sched, model=model)
    sys_.loop.run(PUSH_T)
    model.perturb(PUSH)
    sys_.loop.run(4.0)
    return sys_.recorder


def main(render: bool = True) -> None:
    recs = {"active balance": _run(True), "passive only": _run(False)}

    print("=== BALANCE RECOVERY after a trunk push (MuJoCo) ===")
    i_push = int(PUSH_T / 0.005)
    for label, rec in recs.items():
        tr = [p["trunk"] for p in rec.pose]
        peak = max(abs(x) for x in tr[i_push : i_push + 200])
        final = np.mean([abs(x) for x in tr[-200:]])
        gs = [g for g in rec.gait_state if g is not None][i_push:]
        bal = sum(g.balance_ok for g in gs) / max(1, len(gs))
        print(f"  {label:16s} peak tilt={peak:5.1f} deg  recovered={final:4.1f} deg  "
              f"balance_ok_after={bal:.2f}")
    print("interpretation: the active closed loop rejects the push and returns the "
          "trunk to upright; passive support alone tips much further.")

    if render:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 4))
        for label, rec in recs.items():
            ax.plot(rec.t, [p["trunk"] for p in rec.pose], label=label, lw=1.5)
        ax.axvline(PUSH_T, color="0.5", ls="--", lw=1, label="push")
        ax.axhline(0, color="0.8", lw=0.8)
        ax.set_xlabel("time (s)")
        ax.set_ylabel("trunk tilt (deg)")
        ax.set_title("Active balance recovery vs passive support  [SIMULATION — ILLUSTRATIVE]")
        ax.legend()
        ax.grid(alpha=0.3)
        out = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "balance_recovery.png")
        fig.tight_layout()
        fig.savefig(out, dpi=110)
        plt.close(fig)
        print("saved:", out)


if __name__ == "__main__":
    main()
