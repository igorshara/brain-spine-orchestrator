"""Demo: recovery program management — SSoT + weekly digest (agent-fleet core).

Демо системи управління відновленням. Засіває єдине джерело правди реалістичними
даними (метрики функцій у динаміці, реабілітаційні сесії, рекомендована стим-програма,
дослідницькі ліди, партнери, задачі) і друкує щотижневий зріз. Це детермінований
кістяк агентного флоту-прискорювача; LLM-наратив додається при ANTHROPIC_API_KEY.

Запуск:  python3 scenarios/recovery_demo.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401

from bso.recovery import RecoveryDB, llm_available, weekly_digest


def seed(db: RecoveryDB) -> None:
    weeks = ["2026-04-06", "2026-04-13", "2026-04-20", "2026-04-27", "2026-05-04", "2026-05-11"]
    # function metrics (0..10), illustrative gradual improvement with rehab+EES
    traj = {"movement": [1.0, 1.0, 1.5, 2.0, 2.5, 3.0], "bladder": [2.0, 2.0, 2.5, 3.0, 3.5, 4.0],
            "bowel": [3.0, 3.0, 3.0, 3.5, 3.5, 4.0], "erectile": [1.0, 1.0, 1.0, 1.5, 1.5, 2.0]}
    for dom, vals in traj.items():
        for d, v in zip(weeks, vals, strict=True):
            db.log_metric(d, dom, v, note="self/clinician score")
    pid = db.save_program("2026-05-11", "left knee flexion", contact=6, amplitude_mA=5,
                          pulse_width_us=300, frequency_Hz=40, response=0.56,
                          note="from clinical decision-support session")
    for d in weeks[-3:]:
        db.log_session(d, "activity-based rehab + EES", 60, program_id=pid, notes="Verita protocol")
    db.add_lead("Walking naturally after SCI using a brain-spine interface", "Lorach 2023, Nature",
                "https://www.nature.com/articles/s41586-023-06094-5", "хода — цільова", "reading")
    db.add_lead("Lumbosacral scES improves voiding function", "Louisville, Sci Reports 2018",
                "https://www.nature.com/articles/s41598-018-26602-2", "міхур — цільова", "contact")
    db.add_lead("Activity-dependent neuromodulation (ARC-IM)", "Rowald 2022, Nat Medicine",
                "https://www.nature.com/articles/s41591-021-01663-5", "хода/платформа", "new")
    db.add_partner("Verita Neuro", "Bangkok clinic (Medtronic Intellis)", "meeting upcoming",
                   "demo decision-support tool, propose joint pilot")
    db.add_partner("NeuroRestore (Courtine/Bloch)", "EPFL/CHUV", "to contact",
                   "outreach with brief + GP-BO hook")
    db.add_partner("Medtronic / Boston Scientific", "device makers", "early talks",
                   "explore orchestration layer on platform")
    db.add_task("Показати Verita decision-support + дашборд наживо", "Ihor", "2026-05-18")
    db.add_task("Запросити у Verita EES-протокол і дані телеметрії Intellis", "Ihor", "2026-05-20")
    db.add_task("Скласти план activity-based реабілітації з клініцистом", "Ihor", "2026-05-22")


def main() -> None:
    out = os.path.abspath(_bootstrap.OUTPUT_DIR)
    db = RecoveryDB(os.path.join(out, "recovery.db"))
    # fresh demo: clear tables then seed
    for t in ("metrics", "sessions", "programs", "leads", "partners", "tasks"):
        db.conn.execute(f"DELETE FROM {t}")
    db.conn.commit()
    seed(db)
    brief = weekly_digest(db)
    print(brief)
    print(f"\n[LLM narrative: {'on' if llm_available() else 'off (add ANTHROPIC_API_KEY)'}]")
    with open(os.path.join(out, "recovery_brief.md"), "w") as f:
        f.write(brief)
    print("saved:", os.path.join(out, "recovery_brief.md"))


if __name__ == "__main__":
    main()
