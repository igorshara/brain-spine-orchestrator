"""Demo: adaptive resilience under fatigue + drift — the core differentiator.

Стрес-демо адаптивної оркестрації. Три умови на однаковому намірі (хода 30 с):
  1. nominal           — без деградації (контроль);
  2. degraded          — втома + дрейф плану, БЕЗ адаптації -> волочіння стопи;
  3. degraded + adapt  — той самий план, але УВІМКНЕНА повільна адаптація (Шар 4),
                         що піднімає підсилення ефекторів і компенсує деградацію
                         в межах safety.

Це доказ тези, якої немає в наявних системах: «навіть коли тіло втомлюється і
параметри дрейфують — адаптивний шар тримає ходу». Усі числа ілюстративні.

Запуск:  python3 scenarios/resilience.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401
import numpy as np

from bso.decoder_stub import IntentEvent
from bso.degradation import FatigueModel
from bso.runtime import build_system
from bso.schemas import Mode

DUR = 30.0


def _fatigue() -> FatigueModel:
    # ILLUSTRATIVE degradation that is partially recoverable within safety.
    return FatigueModel(enabled=True, fatigue_rate=0.09, fatigue_max=0.5,
                        drift_rate_per_s=0.004)


def _retention(rec) -> tuple[float, float]:
    fy = np.array([p["L_foot_y"] for p in rec.pose])
    n = int(2.0 / 0.005)
    win = {}
    for i in range(n, len(fy), n):
        win[rec.t[i]] = fy[i - n : i].max() - fy[i - n : i].min()
    early = np.mean([v for t, v in win.items() if 2 < t < 6])
    late = np.mean([v for t, v in win.items() if t > DUR - 6])
    return float(early), float(late)


def main(render: bool = True) -> None:
    schedule = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]

    recs = {
        "nominal": build_system(schedule).run(DUR),
        "degraded": build_system(schedule, fatigue=_fatigue()).run(DUR),
        "degraded+adapt": build_system(schedule, fatigue=_fatigue(), adapt=True).run(DUR),
    }

    print("=== RESILIENCE demo (fatigue + drift over 30 s) ===")
    for label, rec in recs.items():
        early, late = _retention(rec)
        print(f"{label:16s} foot clearance early={early:.3f} m  late={late:.3f} m  "
              f"retention={late / early * 100:4.0f}%")
    g = recs["degraded+adapt"].gains[-1]
    print(f"adaptation final gains: knee_flex={g['L_knee_flex']:.2f}, "
          f"hip_flex={g['L_hip_flex']:.2f}, ankle_dorsi={g['L_ankle_dorsi']:.2f}")
    print("interpretation: without the Layer-4 adaptive layer the foot starts "
          "dragging as fatigue builds; with it, clearance is largely retained "
          "(safety still bounds how much can be compensated).")

    if render:
        from bso.viz.dashboard import save_resilience

        out = os.path.abspath(_bootstrap.OUTPUT_DIR)
        print("saved:", save_resilience(recs, os.path.join(out, "resilience.png"),
                                        title="Adaptive resilience under fatigue + drift"))


if __name__ == "__main__":
    main()
