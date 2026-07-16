"""Demo: clinical decision-support mapping session (clinician-in-the-loop).

Демо інструменту підтримки рішень. Симулюємо сесію клініциста: інструмент пропонує
конфігурацію → «клініцист» застосовує її (тут — симульована відповідь м'яза) →
записує → інструмент пропонує наступну. Показуємо, що добра конфігурація знаходиться
за МАЛО проб на пацієнті (реальна цінність — менше проб, менше часу/дискомфорту).

Інструмент НЕ стимулює — лише радить; усі параметри в межах безпеки. ILLUSTRATIVE.
Для реального використання responses вводить клініцист (input), не симуляція.

Запуск:  python3 scenarios/clinical_assistant.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401
import numpy as np

from bso.clinical_mapping import ClinicalMappingSession, StimConfig


def _simulated_clinician_response(cfg: StimConfig, best_contact=7, rng=None) -> float:
    """Stand-in for what a clinician would observe (target activation − discomfort).
    Hidden surface: a specific contact + charge window is best; over-charge hurts."""
    charge = cfg.amplitude_mA * cfg.pulse_width_us / 250.0
    selectivity = np.exp(-((cfg.contact - best_contact) / 1.3) ** 2)
    activation = 1.0 / (1.0 + np.exp(-1.5 * (charge - 3.0)))
    discomfort = max(0.0, charge - 6.0) * 0.15
    val = selectivity * activation - discomfort
    if rng is not None:
        val += float(rng.normal(0, 0.02))
    return float(np.clip(val, 0.0, 1.0))


def main(render: bool = True) -> None:
    rng = np.random.default_rng(0)
    s = ClinicalMappingSession(n_contacts=16, target="left knee flexion")
    print("=== CLINICAL DECISION-SUPPORT mapping session (clinician-in-the-loop) ===")
    print("  tool proposes safe configs; 'clinician' observes response; tool learns.\n")
    best_so_far = []
    for step in range(1, 13):
        cfg = s.suggest_next()
        resp = _simulated_clinician_response(cfg, rng=rng)
        s.record(cfg, resp, note="simulated response")
        best_so_far.append(s.best().response)
        print(f"  trial {step:2d}: contact {cfg.contact:2d}, {cfg.amplitude_mA:.0f} mA, "
              f"{cfg.pulse_width_us:.0f} us -> response {resp:.2f}  (best {s.best().response:.2f})")

    b = s.best().config
    print(f"\n  recommended after 12 trials: contact {b.contact}, {b.amplitude_mA:.0f} mA, "
          f"{b.pulse_width_us:.0f} us (vs hundreds of configs in a manual sweep)")
    print("  -> fewer trials on the patient = less time and discomfort. Decision support "
          "only; the clinician applies and confirms every setting.")

    out = os.path.abspath(_bootstrap.OUTPUT_DIR)
    with open(os.path.join(out, "clinical_session_report.md"), "w") as f:
        f.write(s.report())
    print("saved report:", os.path.join(out, "clinical_session_report.md"))

    if render:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.plot(range(1, len(best_so_far) + 1), best_so_far, "o-", color="tab:green")
        ax.set_xlabel("clinician trial (one applied configuration)")
        ax.set_ylabel("best response found")
        ax.set_title("Decision-support mapping converges in a handful of clinician trials\n"
                     "[clinician-in-the-loop · no device control · ILLUSTRATIVE]", fontsize=10.5)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(out, "clinical_assistant.png"), dpi=110)
        plt.close(fig)
        print("saved:", os.path.join(out, "clinical_assistant.png"))


if __name__ == "__main__":
    main()
