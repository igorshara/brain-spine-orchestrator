"""Hand pacer — the patient's arms set the step cadence.

Винахід ІЗАР #3: декодер ніг після травми ненадійний. А РУКИ збережені (висока
sparing) і дають чистий ритм. Ідея: phase-lock годинника ходи до ритму рук, а не
до (зміщеного) декодера ніг. Тоді каданс іде за справжнім наміром пацієнта, навіть
коли декодер ніг бреше.

Сценарій чесний: декодер ніг застряг на ФІКСОВАНІЙ швидкості (каданс ≈60), а
пацієнт у середині прогулянки ПРИШВИДШУЄТЬСЯ до 84. Дивимось, хто з двох контурів
дає правильний каданс:
  - free-running (cadence_source=intent): іде за зміщеним декодером;
  - hand-paced (cadence_source=manual): іде за ритмом рук.

Двійник: BSO closed loop. Каданс міряємо за фактичними обертами фази ходи (не за
тим, що контур «декларує»). Усе ILLUSTRATIVE.

Запуск:  python3 scenarios/hand_pacer.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bso.decoder_stub import IntentEvent  # noqa: E402
from bso.runtime import build_system  # noqa: E402
from bso.schemas import Mode  # noqa: E402

DT, DUR = 0.005, 12.0
T_CHANGE = 6.0
TRUE_BEFORE, TRUE_AFTER = 60.0, 84.0     # patient's real intended cadence (steps/min)
DECODER_SPEED = 0.333                     # leg decoder stuck here -> cadence ~60 always


def true_cadence(t):
    return TRUE_BEFORE if t < T_CHANGE else TRUE_AFTER


def _run(hand: bool):
    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=DECODER_SPEED)]
    kw = {"hand_cadence": true_cadence} if hand else {}
    return build_system(sched, dt=DT, **kw).run(DUR)


def _achieved_cadence(rec, t0, t1):
    """Steps/min from actual gait-phase wraps in [t0,t1] (2 steps per cycle)."""
    cycles = 0.0
    prev = None
    span = 0.0
    for i, t in enumerate(rec.t):
        if not (t0 <= t <= t1):
            continue
        cp = (rec.gait_phase[i] or {}).get("cycle_phase")
        if cp is None:
            continue
        if prev is not None:
            d = cp - prev
            if d < -0.5:          # wrapped past 1.0
                d += 1.0
            cycles += max(0.0, d)
        prev = cp
        span = t
    minutes = (t1 - t0) / 60.0
    return round(2.0 * cycles / max(minutes, 1e-9), 1)


def main():
    print(f"Hand pacer — leg decoder stuck at ~{TRUE_BEFORE:.0f} steps/min; patient "
          f"speeds up to {TRUE_AFTER:.0f} at t={T_CHANGE:.0f}s. Cadence measured from "
          f"actual gait-phase wraps. ILLUSTRATIVE.\n")
    print(f"{'arm':<28}{'before (true 60)':>18}{'after (true 84)':>18}")
    print("-" * 64)
    res = {}
    for label, hand in (("free-running (leg decoder)", False), ("hand-paced (arm rhythm)", True)):
        rec = _run(hand)
        before = _achieved_cadence(rec, 2.0, T_CHANGE - 0.5)
        after = _achieved_cadence(rec, T_CHANGE + 1.0, DUR - 0.5)
        res[hand] = (before, after)
        print(f"{label:<28}{before:>18}{after:>18}")
    print("-" * 64)
    fb_err = abs(res[False][1] - TRUE_AFTER)
    hp_err = abs(res[True][1] - TRUE_AFTER)
    print(f"\nAfter the speed-up: free-running off by {fb_err:.0f} steps/min, "
          f"hand-paced off by {hp_err:.0f}.")
    if hp_err < fb_err:
        print("→ The hand pacer follows the patient's real intent through the "
              "unreliable leg decoder. The arms carry the rhythm the legs lost.")
    else:
        print("→ No tracking advantage here — honest negative.")


if __name__ == "__main__":
    main()
