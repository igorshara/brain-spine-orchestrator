"""Demo: closed-loop bladder management — automatic, AD-safe voiding.

Демо замкнутого контуру міхура. Контролер із сенсором наповнення сам спорожняє
міхур (за обʼємом — ДО неінгібованого рефлексу), тримаючи тиск безпечним і
ПОВНІСТЮ відвертаючи автономну дисрефлексію — упродовж багатьох циклів за сесію.
Порівнюємо з некерованою дисинергією (рефлекторне спорожнення при високому тиску →
повторні епізоди АД). Усе ILLUSTRATIVE.

Потрібен matplotlib. Запуск:  python3 scenarios/managed_bladder.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401

from bso.autonomic import (
    AutonomicCommand,
    AutonomicEvent,
    AutonomicFunction,
    build_autonomic_system,
    build_managed_bladder_system,
)
from bso.safety import SafetySupervisor

DUR = 600.0


def main(render: bool = True) -> None:
    s_man = SafetySupervisor()
    managed = build_managed_bladder_system(modulation=True, safety=s_man)
    log_man = [x for x in managed.run(DUR) if x and x["function"] == "bladder"]

    s_un = SafetySupervisor()
    unmanaged = build_autonomic_system(
        [AutonomicEvent(0.0, AutonomicFunction.BLADDER, AutonomicCommand.STORE)],
        modulation=False, dyssynergia=True, safety=s_un)
    log_un = [x for x in unmanaged.run(DUR) if x and x["function"] == "bladder"]

    print("=== CLOSED-LOOP BLADDER MANAGEMENT (10-min session) ===")
    print(f"  managed (auto-void):   voids={managed.manager.void_count}, "
          f"peak P={max(x['pressure'] for x in log_man):.0f} cmH2O, "
          f"max vol={max(x['volume'] for x in log_man):.0f} mL, "
          f"AD events={s_man.autonomic_ad_events}")
    print(f"  unmanaged dyssynergia: peak P={max(x['pressure'] for x in log_un):.0f} cmH2O, "
          f"max vol={max(x['volume'] for x in log_un):.0f} mL, "
          f"AD events={s_un.autonomic_ad_events}")
    print("  -> the controller voids before the pathological reflex, keeping pressure")
    print("     safe and preventing autonomic dysreflexia across every cycle.")

    if render:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        t_man = [i * 0.1 for i in range(len(log_man))]
        t_un = [i * 0.1 for i in range(len(log_un))]
        fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
        fig.suptitle("Closed-loop bladder management vs unmanaged dyssynergia\n"
                     "[RESEARCH SIMULATION — ILLUSTRATIVE]", fontsize=12)
        ax[0].plot(t_man, [x["volume"] for x in log_man], color="tab:green",
                   label="managed (auto-void)")
        ax[0].plot(t_un, [x["volume"] for x in log_un], color="tab:red", label="unmanaged")
        ax[0].set_ylabel("bladder volume (mL)")
        ax[0].set_title("Volume — managed saw-tooth (regular emptying) vs unmanaged plateau")
        ax[0].legend()
        ax[0].grid(alpha=0.3)
        ax[1].plot(t_man, [x["pressure"] for x in log_man], color="tab:green", label="managed")
        ax[1].plot(t_un, [x["pressure"] for x in log_un], color="tab:red", label="unmanaged")
        ax[1].axhline(60, color="0.6", ls=":", lw=1, label="AD trigger 60")
        ax[1].axhline(40, color="0.6", ls="--", lw=1, label="safe void <40")
        ax[1].set_ylabel("detrusor pressure (cmH2O)")
        ax[1].set_xlabel("time (s)")
        ax[1].set_title("Pressure — managed stays safe; unmanaged spikes into the AD zone")
        ax[1].legend()
        ax[1].grid(alpha=0.3)
        out = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "managed_bladder.png")
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        fig.savefig(out, dpi=110)
        plt.close(fig)
        print("saved:", out)


if __name__ == "__main__":
    main()
