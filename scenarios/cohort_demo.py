"""Demo: cohort meta-learned mapping prior — warm-start a new patient. Idea 3.

Холодний старт (з нуля) проти теплого старту (пріор із когорти) для мапінгу нового
пацієнта. Тепло-старт дає велику фору при нулі/малій кількості проб. Усе ILLUSTRATIVE.

Запуск:  python3 scenarios/cohort_demo.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401
import numpy as np

from bso.cohort import warm_vs_cold


def _probes_to(budgets, acc, target=0.75):
    for b, a in zip(budgets, acc, strict=True):
        if a >= target:
            return b
    return budgets[-1]


def main(render: bool = True) -> None:
    budgets, cold, warm = warm_vs_cold(n_cohort=12)
    print("=== Cohort meta-learned prior: warm-start a new patient's mapping ===")
    print(f"  free accuracy from prior (0 probes): cold {cold[0] * 100:.0f}% "
          f"vs warm {warm[0] * 100:.0f}%")
    print(f"  probes to reach 75%: cold {_probes_to(budgets, cold)} "
          f"vs warm {_probes_to(budgets, warm)}")
    print("  -> the cohort gives a big head-start; every prior patient makes the next "
          "mapping faster (the 1TMO flywheel). Honest: prior quality tracks cohort "
          "similarity, not raw size.")

    if render:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 4.8))
        ax.plot(budgets, np.array(warm) * 100, "o-", color="tab:green",
                label="warm-start (cohort prior)")
        ax.plot(budgets, np.array(cold) * 100, "o-", color="tab:gray",
                label="cold-start (from scratch)")
        ax.set_xlabel("probes on the new patient (clinician trials)")
        ax.set_ylabel("best-contact mapping accuracy (%)")
        ax.set_title("Cohort prior warm-starts mapping — fewer probes on the new patient\n"
                     "[RESEARCH SIMULATION, ILLUSTRATIVE]", fontsize=11)
        ax.legend()
        ax.grid(alpha=0.3)
        out = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "cohort_prior.png")
        fig.tight_layout()
        fig.savefig(out, dpi=110)
        plt.close(fig)
        print("saved:", out)


if __name__ == "__main__":
    main()
