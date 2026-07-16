"""Demo: optimize RECOVERY (stim-OFF), not function (stim-ON). Idea 1 of the vision.

Порівнюємо два курси реабілітації по 30 сесій: «функція-перша» (кранить асист, ігнорує
таймінг) проти «відновлення-перша» (шукає оптимальний таймінг пластичності й парує).
Міряємо РЕАЛЬНЕ одужання — функцію з ВИМКНЕНОЮ стимуляцією. Усе ILLUSTRATIVE.

Запуск:  python3 scenarios/plasticity_demo.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401

from bso.plasticity import function_first_course, recovery_first_course


def main(render: bool = True) -> None:
    ff, ff_on = function_first_course(n_sessions=30, tau_opt_ms=20.0)
    rf, best = recovery_first_course(n_sessions=30, tau_opt_ms=20.0)
    print("=== Optimize recovery, not function (stim-OFF outcome after 30 sessions) ===")
    print(f"  function-first (assist, ignore timing): stim-OFF recovery={ff[-1]:.2f} "
          f"(looks fine with stim ON={ff_on:.2f})")
    print(f"  recovery-first (find timing, pair):      stim-OFF recovery={rf[-1]:.2f} "
          f"(found timing {best:.0f} ms ~ true 20 ms)")
    print(f"  -> {(rf[-1] / max(ff[-1], 1e-6) - 1) * 100:.0f}% more real healing by optimizing "
          "plasticity (pairing/timing), not compensation.")

    if render:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 4.8))
        ax.plot(range(1, len(rf) + 1), rf, "o-", color="tab:green", label="recovery-first")
        ax.plot(range(1, len(ff) + 1), ff, "o-", color="tab:red", label="function-first")
        ax.set_xlabel("rehab session")
        ax.set_ylabel("voluntary function, stim OFF (recovery)")
        ax.set_title("Optimizing recovery (not stim-ON function) heals far more\n"
                     "[plasticity curriculum · RESEARCH SIMULATION, ILLUSTRATIVE]", fontsize=11)
        ax.legend()
        ax.grid(alpha=0.3)
        out = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "plasticity.png")
        fig.tight_layout()
        fig.savefig(out, dpi=110)
        plt.close(fig)
        print("saved:", out)


if __name__ == "__main__":
    main()
