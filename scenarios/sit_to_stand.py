"""Demo: sit-to-stand transition with balance hold.

Демо «сидячи -> стоячи»: режим SIT (стегно/коліно зігнуті) -> STAND (розгиначі
+ гомілковостоп + стабілізатори тулуба наростають), утримання рівноваги.

Запуск:  python3 scenarios/sit_to_stand.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401

from bso.decoder_stub import IntentEvent
from bso.runtime import build_system
from bso.schemas import Mode


def main(render: bool = True) -> None:
    schedule = [
        IntentEvent(0.0, Mode.SIT),
        IntentEvent(2.0, Mode.STAND),
    ]
    sys_ = build_system(schedule, dt=0.005)
    rec = sys_.run(6.0)

    # Knee angle: large (flexed) while sitting -> small (extended) when standing.
    knee_sit = rec.pose[int(1.5 / 0.005)]["L_knee"]
    knee_stand = rec.pose[-1]["L_knee"]
    gs = [g for g in rec.gait_state if g is not None]
    balance_ratio = sum(g.balance_ok for g in gs) / len(gs)

    print("=== SIT-TO-STAND demo ===")
    print(f"L_knee while sitting: {knee_sit:.1f} deg -> standing: {knee_stand:.1f} deg")
    print(f"knee extended on stand: {'yes' if knee_stand < knee_sit - 10 else 'no'}")
    print(f"balance ok ratio: {balance_ratio:.2f}")
    print(f"safety events: {len(rec.safety_events)}")

    if render:
        from bso.viz.dashboard import save_animation, save_summary

        out = os.path.abspath(_bootstrap.OUTPUT_DIR)
        print("saved:", save_summary(rec, os.path.join(out, "sit_to_stand_summary.png"),
                                      title="SIT -> STAND"))
        print("saved:", save_animation(rec, os.path.join(out, "sit_to_stand.gif"),
                                        stride=6, title="SIT -> STAND"))


if __name__ == "__main__":
    main()
