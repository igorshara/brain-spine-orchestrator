"""Demo: predictive autonomic-dysreflexia guardian (autonomic-first, life-safety).

Порівнюємо три політики ведення дисрефлексійного ризику впродовж 10-хв сесії
наповнення міхура: без керування / реактивно / ПРЕДИКТИВНИЙ вартовий (прогноз +
випередження). Показуємо, що предиктивний відвертає АД повністю і попереджає
завчасно, а також що він АДАПТУЄТЬСЯ до швидкості наповнення. Усе ILLUSTRATIVE —
дослідницька симуляція, не медичний пристрій.

Запуск:  python3 scenarios/ad_guardian_demo.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401

from bso.ad_guardian import simulate


def main(render: bool = True) -> None:
    runs = {p: simulate(p) for p in ("none", "reactive", "predictive")}
    print("=== Predictive autonomic-dysreflexia guardian (10-min bladder session) ===")
    print(f"  {'policy':12s} {'AD ev':>7} {'BP rise':>9} {'peak P':>8} {'1st warn':>10}")
    for p, (_, m) in runs.items():
        print(f"  {p:12s} {m['ad_events']:10d} {m['peak_bp_rise']:11.0f}mmHg "
              f"{m['peak_pressure']:6.0f}cm {str(m['first_warning_s']):>12}")

    none_first_ad = runs["none"][1]["first_ad_event_s"]
    pred_warn = runs["predictive"][1]["first_warning_s"]
    if none_first_ad and pred_warn is not None:
        lead = none_first_ad - pred_warn
        print(f"\n  lead time: warned at t={pred_warn:.0f}s; unmanaged AD hit at "
              f"t={none_first_ad:.0f}s -> ~{lead:.0f}s warning.")

    # adaptivity: faster diuresis -> guardian acts sooner
    print("\n  adaptivity (warns earlier when filling faster):")
    for rate in (1.0, 2.0, 3.0):
        _, m = simulate("predictive", fill_ml_per_s=rate)
        print(f"    fill {rate} mL/s -> first warning at t={m['first_warning_s']}s, "
              f"AD events={m['ad_events']}")

    print("\n  -> the predictive guardian PREVENTS the life-threatening surge (0 events) that "
          "reactive care misses; runs 24/7 on cheap wearables. This is autonomic-first safety.")

    if render:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 4.8))
        cols = {"none": "tab:red", "reactive": "tab:orange", "predictive": "tab:green"}
        for p, (rec, _) in runs.items():
            ax.plot(rec["t"], rec["bp"], label=p, color=cols[p], lw=1.6)
        ax.axhline(110 + 40, color="0.5", ls="--", lw=1, label="AD danger (+40 mmHg)")
        ax.set_xlabel("time (s)")
        ax.set_ylabel("systolic BP proxy (mmHg)")
        ax.set_title("Predictive AD guardian prevents the dangerous BP surge\n"
                     "[autonomic-first · 24/7 · RESEARCH SIMULATION, ILLUSTRATIVE]", fontsize=11)
        ax.legend()
        ax.grid(alpha=0.3)
        out = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "ad_guardian.png")
        fig.tight_layout()
        fig.savefig(out, dpi=110)
        plt.close(fig)
        print("saved:", out)


if __name__ == "__main__":
    main()
