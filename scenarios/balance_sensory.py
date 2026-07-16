"""Sensory closed loop — restoring the rate-of-sway signal keeps you standing.

Винахід ІЗАР #5: стояння = обернений маятник. Порівнюємо три сенсорні режими під
однаковими поштовхами: без відчуття / лише позиція / позиція+швидкість
(пропріоцепція). Усе ILLUSTRATIVE.

Запуск:  python3 scenarios/balance_sensory.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bso.balance_sensory import compare  # noqa: E402

LABEL = {"off": "no sensation (open loop)",
         "reactive": "position only",
         "proprioceptive": "position + velocity (proprioception)"}


def main():
    r = compare()
    print(f"Sensory closed loop — standing as an inverted pendulum, equal lateral "
          f"pushes. Fall threshold {r['fall_deg']} deg. ILLUSTRATIVE.\n")
    print(f"{'sensory mode':<42}{'max tilt deg':>14}{'outcome':>12}")
    print("-" * 68)
    for m in ("off", "reactive", "proprioceptive"):
        d = r["modes"][m]
        out = "STANDS" if d["upright"] else "FALLS"
        print(f"{LABEL[m]:<42}{d['max_tilt_deg']:>14}{out:>12}")
    print("-" * 68)
    print("\n→ Position alone cannot stabilise an inverted pendulum — the body needs "
          "the RATE of sway (proprioception) to catch the fall early. Restoring that "
          "sensory channel is what turns falling into standing.")


if __name__ == "__main__":
    main()
