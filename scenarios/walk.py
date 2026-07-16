"""Demo: rhythmic closed-loop walking + a balance perturbation.

Демо ходи: стояння -> хода із замкнутим контуром -> ін'єкція збурення рівноваги
на 5-й секунді -> видиме відновлення балансу. Логує намір -> фази -> активації ->
стим-команди (після safety) -> сенсори, і зберігає зведену панель + анімацію.

Запуск:  python3 scenarios/walk.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401  (sets sys.path)

from bso.decoder_stub import IntentEvent
from bso.runtime import build_system
from bso.schemas import Mode


def main(render: bool = True) -> None:
    schedule = [
        IntentEvent(0.0, Mode.STAND),
        IntentEvent(1.0, Mode.WALK, speed=0.6),
    ]
    sys_ = build_system(schedule, dt=0.005)

    # Run to t=5s, inject a forward trunk perturbation, then continue.
    sys_.loop.run(5.0)
    sys_.model.trunk_tilt += 14.0  # external push (deg) — disturbance
    sys_.loop.run(7.0)
    rec = sys_.recorder

    gs = [g for g in rec.gait_state if g is not None]
    balance_ratio = sum(g.balance_ok for g in gs) / len(gs)
    worst_tilt = max(abs(g.trunk_tilt_deg) for g in gs)
    final_tilt = gs[-1].trunk_tilt_deg

    print("=== WALK demo ===")
    print(f"duration: {rec.t[-1]:.1f}s, steps simulated: {len(rec.t)}")
    print(f"estimated cadence (final): {gs[-1].cadence:.0f} steps/min")
    print(f"balance ok ratio: {balance_ratio:.2f}")
    print(f"worst trunk tilt after push: {worst_tilt:.1f} deg, recovered to {final_tilt:.1f} deg")
    print(f"safety events: {len(rec.safety_events)}")

    if render:
        from bso.viz.dashboard import save_animation, save_summary

        out = os.path.abspath(_bootstrap.OUTPUT_DIR)
        p1 = save_summary(rec, os.path.join(out, "walk_summary.png"), title="WALK + perturbation")
        p2 = save_animation(rec, os.path.join(out, "walk.gif"), stride=8, title="WALK")
        print("saved:", p1)
        print("saved:", p2)


if __name__ == "__main__":
    main()
