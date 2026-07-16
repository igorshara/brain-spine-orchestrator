"""Shadow Step, validated on the OpenSim model — real anatomy, real muscles.

Найчесніша перевірка винаходу: беремо активації, що їх породжує замкнутий контур
на Hill-двійнику (reactive vs predictive), і проганяємо їх через ВАЛІДОВАНУ
м'язово-скелетну модель OpenSim (gait10dof18musc, 18 м'язів Хілла, реальна кістка),
де рух — це forward dynamics від сил м'язів. Міряємо кліренс носка на справжній
анатомії. Якщо тіньовий крок піднімає стопу вище й тут — механізм тримається не
лише на спрощеному двійнику.

Запуск:  python3 scenarios/predictive_opensim.py   (потрібен OpenSim 4.x)
Усе ILLUSTRATIVE — дослідницька симуляція, не клінічні числа.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bso.biomech.kinematic import KinematicModel  # noqa: E402
from bso.decoder_stub import IntentEvent  # noqa: E402
from bso.runtime import build_system  # noqa: E402
from bso.schemas import Mode  # noqa: E402

T_START, DURATION = 4.0, 3.0
LOW_CLEAR_M = 0.03   # toe below this (m) on the validated model = poor clearance


def _activations(mode: str):
    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]
    s = build_system(sched, dt=0.005, model=KinematicModel(use_muscles=True))
    s.feedback.mode = mode
    s.feedback.lead_ms, s.feedback.pred_gain, s.feedback.pred_tail_gain = 100.0, 1.5, 0.5
    rec = s.run(T_START + DURATION + 1.0)
    return rec.activations, rec.t


def _opensim_metrics(mode: str) -> dict:
    from bso.biomech.opensim_model import run_muscle_driven
    acts, t = _activations(mode)
    res = run_muscle_driven(acts, t, t_start=T_START, duration=DURATION)
    toes = [min(f["l"][-1][1], f["r"][-1][1]) for f in res["figures"]]
    mean_clear = sum(toes) / len(toes)
    low = sum(1 for y in toes if y < LOW_CLEAR_M)
    return {"mean_clear_cm": round(100.0 * mean_clear, 2),
            "low_clear_frames": low, "frames": len(toes)}


def main():
    print(f"Shadow Step on the VALIDATED OpenSim model (18 Hill muscles). "
          f"Window {T_START:.0f}-{T_START+DURATION:.0f}s. ILLUSTRATIVE.\n")
    print(f"{'arm':<14}{'mean_clear_cm':>16}{'low_clear_frames':>20}")
    print("-" * 52)
    res = {}
    for mode in ("reactive", "predictive"):
        m = _opensim_metrics(mode)
        res[mode] = m
        print(f"{mode:<14}{m['mean_clear_cm']:>16}{m['low_clear_frames']:>20}")
    print("-" * 52)
    r, p = res["reactive"], res["predictive"]
    d = round(p["mean_clear_cm"] - r["mean_clear_cm"], 2)
    print(f"\npredictive vs reactive on real anatomy: mean toe clearance "
          f"{r['mean_clear_cm']}→{p['mean_clear_cm']} cm ({d:+} cm), "
          f"low-clearance frames {r['low_clear_frames']}→{p['low_clear_frames']}.")
    if p["mean_clear_cm"] >= r["mean_clear_cm"]:
        print("→ The shadow step lifts the foot higher on the validated model too. "
              "The mechanism holds beyond the simplified twin.")
    else:
        print("→ No gain on the validated model — honest negative; revisit.")


if __name__ == "__main__":
    main()
