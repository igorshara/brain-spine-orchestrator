"""Shadow Step — does feed-forward dorsiflexion beat reactive on the twin?

Винахід ІЗАР «Тіньовий крок»: замість реагувати на провал стопи ПІСЛЯ події,
читаємо фазовий годинник CPG і випереджаємо swing на електромеханічну затримку
(а пізній непотрібний хвіст dorsi — прибираємо). Обхід рубця у ЧАСІ + перерозподіл
зусилля, а не просто «дати більше струму».

Три однакові плечі (off / reactive / predictive): те саме тіло, графік наміру й
safety-ліміти; відрізняється ЛИШЕ шар корекцій. Міряємо:
  - drag%         : частка swing-тіків з волочінням (гомілковостоп нижче порога);
  - min_clear_cm  : найгірший кліренс стопи у swing (більше краще);
  - dorsi_effort  : сумарна dorsi-активація (проксі «скільки стимуляції витратили»).

Два двійники:
  1) Кінематичний МИТТЄВИЙ — тіло реагує без затримки → випереджати нема чого.
  2) Hill-мʼязовий — у мʼяза СВОЯ активаційна динаміка (tau_act/tau_deact),
     тобто фізіологічна затримка виникає сама. Саме її «тіньовий крок» і обходить.

Запуск:  python3 scenarios/predictive_step.py    (усе ILLUSTRATIVE)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bso.biomech.kinematic import KinematicModel  # noqa: E402
from bso.decoder_stub import IntentEvent  # noqa: E402
from bso.feedback import FOOT_DRAG_ANKLE_DEG  # noqa: E402
from bso.runtime import build_system  # noqa: E402
from bso.schemas import Mode  # noqa: E402

DT, DUR, WARMUP_S = 0.005, 16.0, 4.0
SWING_P0, SWING_P1 = 0.60, 1.0
# Tuned shadow-step parameters (see the sweep): redistribute, don't just add.
LEAD_MS, PRED_GAIN, PRED_TAIL = 100.0, 1.5, 0.5


def _run(mode: str, hill: bool):
    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]
    model = KinematicModel(use_muscles=True) if hill else KinematicModel()
    sysm = build_system(sched, dt=DT, model=model)
    fb = sysm.feedback
    fb.mode = mode
    fb.lead_ms, fb.pred_gain, fb.pred_tail_gain = LEAD_MS, PRED_GAIN, PRED_TAIL
    return sysm.run(DUR)


def _metrics(rec):
    drag = swing = 0
    worst = 1e9
    effort = 0.0
    for i, t in enumerate(rec.t):
        if t < WARMUP_S:
            continue
        gp = rec.gait_phase[i] or {}
        cp = gp.get("cycle_phase")
        if cp is None or gp.get("cadence", 0.0) <= 0.0:
            continue
        pose, act = rec.pose[i], (rec.activations[i] or {})
        effort += act.get("L_ankle_dorsi", 0.0) + act.get("R_ankle_dorsi", 0.0)
        for side, lp in (("L", cp), ("R", (cp + 0.5) % 1.0)):
            if not (SWING_P0 <= lp <= SWING_P1):
                continue
            swing += 1
            if pose.get(f"{side}_ankle", 0.0) <= FOOT_DRAG_ANKLE_DEG:
                drag += 1
            worst = min(worst, pose.get(f"{side}_foot_y", 0.0))
    return {"drag_pct": round(100.0 * drag / max(1, swing), 1),
            "min_clear_cm": round(100.0 * worst, 2),
            "dorsi_effort": round(effort, 1)}


def _block(title: str, hill: bool):
    print(f"\n=== {title} ===")
    print(f"{'arm':<32}{'drag%':>8}{'min_clear_cm':>14}{'dorsi_effort':>14}")
    print("-" * 70)
    res = {}
    for label, mode in (("off (open-loop CPG)", "off"),
                        ("reactive (sense-then-correct)", "reactive"),
                        ("predictive (shadow step)", "predictive")):
        m = _metrics(_run(mode, hill))
        res[mode] = m
        print(f"{label:<32}{m['drag_pct']:>8}{m['min_clear_cm']:>14}{m['dorsi_effort']:>14}")
    print("-" * 70)
    r, p = res["reactive"], res["predictive"]
    drag = "↓" if p["drag_pct"] < r["drag_pct"] else ("=" if p["drag_pct"] == r["drag_pct"] else "↑")
    eff = "↓" if p["dorsi_effort"] < r["dorsi_effort"] else ("=" if p["dorsi_effort"] == r["dorsi_effort"] else "↑")
    print(f"predictive vs reactive:  drag {r['drag_pct']}→{p['drag_pct']}% ({drag}),  "
          f"effort {r['dorsi_effort']}→{p['dorsi_effort']} ({eff})")
    return res


def main():
    print(f"Shadow Step — {DUR:.0f}s walk, measured after {WARMUP_S:.0f}s "
          f"(lead {LEAD_MS:.0f} ms, gain {PRED_GAIN}, tail {PRED_TAIL}). ILLUSTRATIVE.")
    _block("instant kinematic twin (no electromechanical delay)", hill=False)
    res = _block("Hill-muscle twin (physiological activation delay)", hill=True)
    r, p = res["reactive"], res["predictive"]
    if p["drag_pct"] < r["drag_pct"] and p["dorsi_effort"] <= r["dorsi_effort"]:
        print("\n→ On the physiological twin the shadow step cuts foot drag with "
              "LESS stimulation. The mechanism is real and conditional on the delay.")
    else:
        print("\n→ No equal-effort win here — report honestly and tune or reconsider.")


if __name__ == "__main__":
    main()
