"""Dual lock — same movement for less charge, no antagonist spillover.

Винахід ІЗАР #4: EES-праймінг (subthreshold, тримає мережу «готовою») + селективна
периферійна добивка. Порівнюємо з одноканальним EES, що мусить перекрити й переливши
струм на антагоніст. Метрика — заряд (∝ амплітуда) і перелив на антагоніст для тієї
ж ЧИСТОЇ сили в суглобі. Свердлимо по коуплінгу (струмовий перелив між контактами).

Запуск:  python3 scenarios/dual_lock.py    (усе ILLUSTRATIVE)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bso.dual_lock import compare  # noqa: E402

TARGET = 0.5


def main():
    print(f"Dual lock — target net joint force = {TARGET}. Charge ~ amplitude (mA), "
          f"equal pulse width. Sweep current-spread coupling. ILLUSTRATIVE.\n")
    print(f"{'coupling':>9}{'single EES charge':>19}{'spillover':>11}"
          f"{'dual-lock charge':>18}{'saving %':>10}")
    print("-" * 67)
    rows = []
    for c in (0.0, 0.1, 0.2, 0.3, 0.4):
        r = compare(TARGET, c)
        s, d = r["single"], r["dual"]
        rows.append(r)
        if s:
            print(f"{c:>9}{s['charge']:>19}{s['spillover']:>11}"
                  f"{d['charge']:>18}{r['charge_saving_pct']:>10}")
        else:
            print(f"{c:>9}{'INFEASIBLE (saturates)':>19}")
    print("-" * 67)
    real = compare(TARGET, 0.3)
    print(f"\nAt realistic current spread (coupling 0.3): single EES needs "
          f"{real['single']['charge']} mA and bleeds {real['single']['spillover']} onto the "
          f"antagonist; dual lock needs {real['dual']['charge']} mA "
          f"({real['charge_saving_pct']}% less) with zero spillover.")
    print("→ The worse the current spread (closely-spaced contacts), the more the "
          "dual lock saves — it directly attacks the problem single-channel EES has.")


if __name__ == "__main__":
    main()
