"""Demo: autonomic neuromodulation — bladder, bowel, erectile function.

Демо автономних функцій (для людей зі спінальною травмою цінуються нарівні або
вище за ходьбу). Показуємо контраст: патологічний рефлекс SCI (дисинергія) проти
координованої EES-нейромодуляції на спільному стимуляційному+safety субстраті.

Сечовий міхур — головний кейс: безпечне спорожнення при низькому тиску й
відвернення автономної дисрефлексії (загроза життю). Усе ILLUSTRATIVE.

Потрібен matplotlib. Запуск:  python3 scenarios/autonomic_demo.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401
import numpy as np

from bso.autonomic import (
    AutonomicCommand,
    AutonomicOrchestrator,
    BowelModel,
    ErectileModel,
    simulate_bladder,
)


def main(render: bool = True) -> None:
    print("=== AUTONOMIC NEUROMODULATION (research simulation, ILLUSTRATIVE) ===\n")

    # --- Bladder: DSD vs coordinated voiding ---
    print("LOWER URINARY TRACT — neurogenic bladder")
    print(f"  {'condition':28s} {'peak P':>8} {'residual':>9} {'AD ev':>7} {'BP rise':>9}")
    runs = {}
    for label, mod in (("dyssynergia (no EES)", False), ("coordinated EES", True)):
        bl, ad, rec = simulate_bladder(modulation=mod)
        runs[label] = (bl, ad, rec)
        void = np.array(rec.bladder_pressure[1200:])
        print(f"  {label:28s} {void.max():6.0f}cm {rec.bladder_volume[-1]:7.0f}mL "
              f"{len(ad.events):10d} {ad.systolic_rise:10.0f}mmHg")
    print("  -> coordination restores low-pressure, COMPLETE emptying and prevents")
    print("     autonomic dysreflexia (a life-threatening BP surge).")

    # --- Bowel ---
    print("\nBOWEL — defecation (evacuation completeness)")
    for label, mod in (("dyssynergia (no EES)", False), ("coordinated EES", True)):
        b = BowelModel()
        orch = AutonomicOrchestrator(modulation=mod)
        for _ in range(600):
            b.dyssynergia = not mod
            b.step(orch.drive_for(AutonomicCommand.VOID), AutonomicCommand.VOID, 0.1)
        print(f"  {label:28s} residual content={b.content:.2f}")

    # --- Erectile ---
    print("\nERECTILE FUNCTION — tumescence")
    for label, mod in (("no stimulation", False), ("parasympathetic EES", True)):
        e = ErectileModel()
        orch = AutonomicOrchestrator(modulation=mod)
        for _ in range(200):
            e.step(orch.drive_for(AutonomicCommand.ENGAGE), AutonomicCommand.ENGAGE, 0.1)
        print(f"  {label:28s} rigidity={e.pressure:.2f}  functional={e.functional}")

    if render:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
        fig.suptitle("Bladder: dyssynergia vs coordinated EES\n"
                     "[RESEARCH SIMULATION — ILLUSTRATIVE values, not clinical]", fontsize=12)
        colors = {"dyssynergia (no EES)": "tab:red", "coordinated EES": "tab:green"}
        for label, (_bl, _ad, rec) in runs.items():
            c = colors[label]
            ax[0].plot(rec.t, rec.bladder_volume, label=label, color=c)
            ax[1].plot(rec.t, rec.bladder_pressure, label=label, color=c)
            ax[2].plot(rec.t, rec.bp, label=label, color=c)
        ax[0].set_ylabel("bladder volume (mL)")
        ax[0].set_title("Volume — coordinated EES empties completely")
        ax[1].axhline(40, color="0.5", ls="--", lw=1, label="safe void <40")
        ax[1].axhline(60, color="0.7", ls=":", lw=1, label="AD trigger >60")
        ax[1].set_ylabel("detrusor pressure\n(cmH2O)")
        ax[1].set_title("Pressure — dyssynergia spikes into the danger zone")
        ax[2].axhline(110 + 40, color="0.6", ls="--", lw=1, label="AD threshold")
        ax[2].set_ylabel("systolic BP proxy\n(mmHg)")
        ax[2].set_title("Autonomic dysreflexia — BP surge prevented by coordination")
        ax[2].set_xlabel("time (s)")
        for a in ax:
            a.legend(fontsize=8)
            a.grid(alpha=0.3)
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        out = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "autonomic_bladder.png")
        fig.savefig(out, dpi=110)
        plt.close(fig)
        print("\nsaved:", out)


if __name__ == "__main__":
    main()
