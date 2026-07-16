"""Use-driven assist — how much help maximises LASTING recovery?

Винахід ІЗАР #2: рівень допомоги (assist) — це регулятор. Якщо стимулятор робить
УСЕ за пацієнта (assist=1), його власні контури майже не вмикаються → активність-
залежна пластичність не працює → відновлення (функція з ВИМКНЕНОЮ стимуляцією)
майже нульове. Якщо допомоги нема (assist=0) — кінцівка спершу ледь рухається, і
успішних «спарувань» наміру з рухом мало. Гіпотеза: оптимум — ВСЕРЕДИНІ, а ще краще
— assist, що ЗГАСАЄ в міру відновлення (assist-as-needed).

Двійник: модель активність-залежної пластичності (plasticity.py), ціль = R, тобто
волева функція зі стимуляцією OFF. Усе ILLUSTRATIVE.

Запуск:  python3 scenarios/use_driven_assist.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bso.plasticity import optimal_assist, use_driven_course  # noqa: E402

N = 40


def main():
    r = optimal_assist(n_sessions=N)
    print(f"Use-driven assist — {N} training sessions, optimal pairing timing. "
          f"R = lasting recovery (stim OFF). ILLUSTRATIVE.\n")
    print(f"{'fixed assist':>14}{'final recovery R':>20}")
    print("-" * 36)
    for a, R in zip(r["assists"], r["final_R"]):
        if round(a * 100) % 10 == 0:                 # print every 0.1
            bar = "█" * int(R * 40)
            star = "  <- best" if abs(a - r["best_assist"]) < 1e-9 else ""
            print(f"{a:>14.2f}{R:>20.4f}  {bar}{star}")
    print("-" * 36)
    print(f"\nNo assist (0.0):     R = {r['no_assist_R']}")
    print(f"Best fixed assist:   R = {r['best_R']}  at assist = {r['best_assist']}")
    print(f"Full assist (1.0):   R = {r['full_assist_R']}   (machine does it all)")
    print(f"Adaptive (fading):   R = {r['adaptive_R']}   (assist-as-needed, a = (1-R)/2)")

    drop = round(r["no_assist_R"] / max(1e-6, r["full_assist_R"]), 1)
    print(f"\n→ Full assist yields ~{drop}x LESS lasting recovery than leaving room "
          f"for the patient's own effort.")
    if 0.0 < r["best_assist"] < 1.0 and r["adaptive_R"] >= r["best_R"]:
        print("→ The optimum is interior, and FADING the assist as recovery grows "
              "beats any fixed level. Actionable protocol: assist-as-needed.")
    else:
        print("→ No interior/adaptive advantage here — report honestly.")


if __name__ == "__main__":
    main()
