"""Demo: automatic electrode→muscle mapping for a 16-contact array.

Демо авто-мапінгу 16-електродного масиву (як у Medtronic Intellis). Клініка робить
це ВРУЧНУ годинами; наш агент будує мапу «контакт → м'яз» автоматично за десятки
проб і обирає оптимальні контакти під кожну рухову ціль. Це прямий гачок для Verita.
Усе ILLUSTRATIVE.

Потрібен matplotlib. Запуск:  python3 scenarios/electrode_mapping.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401
import numpy as np

from bso.mapping import (
    GROUPS,
    ElectrodeArray,
    auto_map,
    best_contact_per_group,
    mapping_accuracy,
    selectivity,
)


def main(render: bool = True) -> None:
    arr = ElectrodeArray()
    W_hat, thresholds, trials = auto_map(arr)
    acc = mapping_accuracy(W_hat, arr.W)
    est = best_contact_per_group(W_hat)
    truth = best_contact_per_group(arr.W)
    manual_guess = {g: i for i, g in enumerate(GROUPS)}  # naive array-order default
    manual_acc = sum(manual_guess[g] == truth[g] for g in GROUPS) / len(GROUPS)
    sel = np.mean([selectivity(arr.W, est[g], gi) for gi, g in enumerate(GROUPS)])

    print("=== AUTOMATIC ELECTRODE MAPPING (16-contact array, e.g. Medtronic Intellis) ===")
    print(f"  automated mapping: best-contact accuracy = {acc * 100:.0f}%  "
          f"in {trials} probe trials (~{trials * 0.5:.0f} s)")
    print(f"  naive manual default guess accuracy = {manual_acc * 100:.0f}%")
    print(f"  mean selectivity of auto-selected contacts = {sel:.2f}")
    print("  -> clinics build this map BY HAND over hours; the agent recovers it "
          "automatically and picks the optimal contact per movement target.")

    if render:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(1, 2, figsize=(13, 6))
        fig.suptitle("Automatic electrode→muscle mapping (16 contacts)\n"
                     "[RESEARCH SIMULATION — ILLUSTRATIVE]", fontsize=12)
        panels = [(arr.W, "ground truth (hidden)"),
                  (W_hat, f"recovered automatically — {acc * 100:.0f}% best-contact")]
        for a, (M, ttl) in zip(ax, panels, strict=True):
            im = a.imshow(M, aspect="auto", cmap="viridis", vmin=0, vmax=1)
            a.set_xticks(range(len(GROUPS)))
            a.set_xticklabels(GROUPS, rotation=90, fontsize=7)
            a.set_yticks(range(arr.n_contacts))
            a.set_ylabel("electrode contact")
            a.set_title(ttl, fontsize=10)
            fig.colorbar(im, ax=a, fraction=0.046, label="recruitment weight")
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        out = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "electrode_mapping.png")
        fig.savefig(out, dpi=110)
        plt.close(fig)
        print("saved:", out)


if __name__ == "__main__":
    main()
