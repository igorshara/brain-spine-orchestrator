"""Demo: stair climbing as an intent-mode change.

Демо сходів: WALK -> STAIRS_UP (вищий згин стегна/коліна для кліренсу сходинки) ->
WALK. Показує, як зміна НАМІРУ перемикає патерн диригента без втручання в safety.

Запуск:  python3 scenarios/stairs.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401

from bso.decoder_stub import IntentEvent
from bso.runtime import build_system
from bso.schemas import Mode


def main(render: bool = True) -> None:
    schedule = [
        IntentEvent(0.0, Mode.WALK, speed=0.5),
        IntentEvent(4.0, Mode.STAIRS_UP, speed=0.5),
        IntentEvent(9.0, Mode.WALK, speed=0.5),
    ]
    sys_ = build_system(schedule, dt=0.005)
    rec = sys_.run(13.0)

    def knee_range(t0, t1):
        i0, i1 = int(t0 / 0.005), int(t1 / 0.005)
        ks = [p["L_knee"] for p in rec.pose[i0:i1]]
        return max(ks) - min(ks), max(ks)

    walk_amp, walk_peak = knee_range(2.0, 4.0)
    stair_amp, stair_peak = knee_range(6.0, 9.0)

    print("=== STAIRS demo ===")
    print(f"L_knee peak flexion — walk: {walk_peak:.1f} deg | stairs: {stair_peak:.1f} deg")
    print(f"higher clearance on stairs: {'yes' if stair_peak > walk_peak + 3 else 'no'}")
    gs = [g for g in rec.gait_state if g is not None]
    print(f"balance ok ratio: {sum(g.balance_ok for g in gs) / len(gs):.2f}")
    print(f"safety events: {len(rec.safety_events)}")

    if render:
        from bso.viz.dashboard import save_animation, save_summary

        out = os.path.abspath(_bootstrap.OUTPUT_DIR)
        print("saved:", save_summary(rec, os.path.join(out, "stairs_summary.png"),
                                      title="WALK -> STAIRS_UP -> WALK"))
        print("saved:", save_animation(rec, os.path.join(out, "stairs.gif"),
                                        stride=8, title="STAIRS"))


if __name__ == "__main__":
    main()
