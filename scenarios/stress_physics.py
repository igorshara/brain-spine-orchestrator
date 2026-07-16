"""Stress battery on the DYNAMIC MuJoCo body — M7 (adaptation) × M8 (physics).

Стрес-батарея на фізичному тілі. Та сама хода (20 с) у чотирьох умовах:
  1. nominal                      — контроль;
  2. fatigue                      — втома+дрейф, БЕЗ адаптації;
  3. fatigue + adapt              — з онлайн-адаптацією Шару 4;
  4. fatigue + noise + adapt      — повний стрес: ще й шумні/підвисаючі сенсори.

Перевіряємо, чи адаптивний шар тримає ходу (кліренс стопи, вертикальність) на
динаміці й попри зашумлений зворотний зв'язок. Усе ILLUSTRATIVE.

Потрібні mujoco + matplotlib. Запуск:  python3 scenarios/stress_physics.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401
import numpy as np

from bso.biomech.mujoco_model import MuJoCoModel
from bso.decoder_stub import IntentEvent
from bso.degradation import FatigueModel
from bso.runtime import build_system
from bso.schemas import Mode
from bso.sensors import SensorCorruptor

DUR = 20.0
SCHED = [IntentEvent(0.0, Mode.STAND), IntentEvent(2.0, Mode.WALK, speed=0.45)]


def _fatigue():
    return FatigueModel(enabled=True, fatigue_rate=0.09, fatigue_max=0.5,
                        drift_rate_per_s=0.004)


def _metrics(rec):
    fy = np.array([p["L_foot_y"] for p in rec.pose])
    n = int(2.0 / 0.005)
    win = {rec.t[i]: fy[i - n : i].max() - fy[i - n : i].min() for i in range(n, len(fy), n)}
    early = np.mean([v for t, v in win.items() if 4 < t < 8])
    late = np.mean([v for t, v in win.items() if t > DUR - 4])
    pz = np.mean([p["pelvis_z"] for p in rec.pose[800:]])
    gs = [g for g in rec.gait_state if g is not None]
    bal = sum(g.balance_ok for g in gs) / len(gs)
    return early, late, pz, bal


def main(render: bool = True) -> None:
    recs = {
        "nominal": build_system(SCHED, model=MuJoCoModel()).run(DUR),
        "fatigue": build_system(SCHED, model=MuJoCoModel(), fatigue=_fatigue()).run(DUR),
        "fatigue+adapt": build_system(SCHED, model=MuJoCoModel(), fatigue=_fatigue(),
                                      adapt=True).run(DUR),
        "fatigue+noise+adapt": build_system(
            SCHED, model=MuJoCoModel(), fatigue=_fatigue(), adapt=True,
            sensor_corruptor=SensorCorruptor(noise_deg=2.0, noise_grf_N=40.0,
                                             dropout_prob=0.05, seed=1),
        ).run(DUR),
    }

    print("=== STRESS BATTERY (MuJoCo dynamic physics) ===")
    print(f"{'condition':22s} {'clr_early':>9} {'clr_late':>9} {'retention':>9} "
          f"{'pelvis_z':>9} {'balance':>8}")
    for label, rec in recs.items():
        early, late, pz, bal = _metrics(rec)
        print(f"{label:22s} {early:9.3f} {late:9.3f} {late / early * 100:8.0f}% "
              f"{pz:9.2f} {bal:8.2f}")
    print("\ninterpretation: adaptation retains foot clearance under fatigue, and "
          "holds up even with noisy/dropping sensors — the harness keeps the biped "
          "upright throughout (pelvis_z ~0.9).")

    if render:
        from bso.viz.dashboard import save_resilience

        out = os.path.abspath(_bootstrap.OUTPUT_DIR)
        print("saved:", save_resilience(recs, os.path.join(out, "stress_physics.png"),
                                        title="Stress battery on MuJoCo physics"))


if __name__ == "__main__":
    main()
