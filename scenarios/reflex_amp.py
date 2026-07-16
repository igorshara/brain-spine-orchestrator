"""Reflex as amplifier — small intent, full support, until clonus.

Винахід ІЗАР #6: EES піднімає підсилення живої рефлекторної петлі нижче травми.
Свердлимо по підсиленню: де мало (не тримає), де вікно (тримає вагу малим наміром),
де клонус (нестабільно). Усе ILLUSTRATIVE.

Запуск:  python3 scenarios/reflex_amp.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bso.reflex_amp import sweep  # noqa: E402


def main():
    s = sweep()
    print(f"Reflex as amplifier — central drive {s['central']} (small), needs support "
          f">= {s['req_support']} to bear weight. ILLUSTRATIVE.\n")
    print(f"{'loop gain':>10}{'support':>10}{'clonus(pp)':>12}  zone")
    print("-" * 52)
    for r in s["rows"]:
        zone = ("✓ weight-bearing" if r["ok"]
                else "clonus (unstable)" if not r["stable"] else "insufficient")
        print(f"{r['gain']:>10}{r['support']:>10}{r['clonus_pp']:>12}  {zone}")
    print("-" * 52)
    w = s["window"]
    if w:
        print(f"\nStable weight-bearing window: gain {w[0]}–{w[1]}. Inside it a small "
              f"central drive of {s['central']} is amplified ~{s['amplification']}x into "
              f"full support — the living reflex does the standing.")
        print("→ EES as a GAIN knob, not a muscle driver: raise the loop just enough "
              "to bear weight, stop below clonus. Cheaper and more natural than "
              "drawing every contraction with current.")
    else:
        print("\nNo stable weight-bearing window — honest negative.")


if __name__ == "__main__":
    main()
