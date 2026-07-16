"""Human-in-the-loop clinical approval.

Makes the "decision support — the clinician decides" stance concrete and auditable:
the system PROPOSES a stimulation change, shows that it sits inside the safety
envelope, and the clinician APPROVES / REJECTS / MODIFIES it. Nothing is ever applied
without an explicit, logged decision, and every proposal is checked against the SAME
SafetySupervisor that guards the real-time loop.

Illustrative research simulation — not a medical device. The clinician, not this
software, decides; this module only surfaces a safe-by-construction suggestion and
records the human decision.
"""
from __future__ import annotations

import hashlib

from .safety import SafetySupervisor
from .schemas import StimCommand

# Deterministic, clinically-framed proposals (ILLUSTRATIVE). Each is a small,
# concrete change a clinician could accept or decline.
_PROPOSALS = {
    "en": [
        {
            "kind": "adaptation",
            "target": "Walking 1 · left hip flexor (contact 3)",
            "summary": "Increase amplitude 13.0 → 14.6 mA (+12%)",
            "rationale": ("Layer-4 adaptation detected fatigue: foot-clearance retention "
                          "fell to 61%. A 12% amplitude increase restores clearance and "
                          "stays inside the safety envelope."),
            "current": {"amplitude_mA": 13.0, "pulse_width_us": 575.0, "frequency_Hz": 88.0, "channel": 3},
            "proposed": {"amplitude_mA": 14.6, "pulse_width_us": 575.0, "frequency_Hz": 88.0, "channel": 3},
        },
        {
            "kind": "mapping",
            "target": "Standing 2 · right knee extensor (GP-BO)",
            "summary": "Try contact 7 at 11.0 mA / 560 µs",
            "rationale": ("Autonomous GP-BO mapping suggests contact 7 (predicted response "
                          "0.82, +0.16 over the current setting). Sample-efficient and safe "
                          "from the first query."),
            "current": {"amplitude_mA": 10.0, "pulse_width_us": 540.0, "frequency_Hz": 22.0, "channel": 5},
            "proposed": {"amplitude_mA": 11.0, "pulse_width_us": 560.0, "frequency_Hz": 22.0, "channel": 7},
        },
    ],
    "ua": [
        {
            "kind": "adaptation",
            "target": "Walking 1 · лівий згинач стегна (контакт 3)",
            "summary": "Підняти амплітуду 13.0 → 14.6 мА (+12%)",
            "rationale": ("Адаптація (Шар 4) виявила втому: утримання кліренсу стопи впало "
                          "до 61%. Підняття амплітуди на 12% відновлює кліренс і лишається "
                          "в межах безпеки."),
            "current": {"amplitude_mA": 13.0, "pulse_width_us": 575.0, "frequency_Hz": 88.0, "channel": 3},
            "proposed": {"amplitude_mA": 14.6, "pulse_width_us": 575.0, "frequency_Hz": 88.0, "channel": 3},
        },
        {
            "kind": "mapping",
            "target": "Standing 2 · правий розгинач коліна (GP-BO)",
            "summary": "Спробувати контакт 7 на 11.0 мА / 560 µs",
            "rationale": ("Автономне GP-BO мапування пропонує контакт 7 (прогноз відгуку "
                          "0.82, +0.16 до поточного). Ефективне за пробами й безпечне з "
                          "першого запиту."),
            "current": {"amplitude_mA": 10.0, "pulse_width_us": 540.0, "frequency_Hz": 22.0, "channel": 5},
            "proposed": {"amplitude_mA": 11.0, "pulse_width_us": 560.0, "frequency_Hz": 22.0, "channel": 7},
        },
    ],
}


N_PROPOSALS = len(_PROPOSALS["en"])


def build_proposal(index: int = 0, lang: str = "en") -> dict:
    """Build one safety-checked proposal. The proposed command is run through the
    SafetySupervisor so the UI can show it is within the envelope BEFORE a clinician
    is asked to approve it."""
    items = _PROPOSALS.get(lang, _PROPOSALS["en"])
    p = {k: (dict(v) if isinstance(v, dict) else v) for k, v in items[index % len(items)].items()}
    pr = p["proposed"]
    v = SafetySupervisor().check(StimCommand(
        t=0.0, channel_id=int(pr["channel"]), amplitude_mA=float(pr["amplitude_mA"]),
        pulse_width_us=float(pr["pulse_width_us"]), frequency_Hz=float(pr["frequency_Hz"])))
    p["safe"] = not v.clamped
    p["charge_uC"] = round(v.command.charge_per_phase_uC, 2)
    if v.clamped:
        p["safety_note"] = (f"would be clamped to {v.command.amplitude_mA:.1f} mA"
                            if lang != "ua" else
                            f"буде обрізано до {v.command.amplitude_mA:.1f} мА")
    else:
        p["safety_note"] = "within safety envelope" if lang != "ua" else "у межах безпеки"
    p["id"] = hashlib.sha1((p["target"] + p["summary"]).encode()).hexdigest()[:8]
    return p


def log_decision(db, ts: str, proposal: dict, decision: str,
                 note: str = "", decided_by: str = "clinician") -> int:
    """Record a clinician decision (approve/reject/modify) in the recovery SSoT."""
    return db._ins("approvals", ts=ts, kind=proposal.get("kind", ""),
                   target=proposal.get("target", ""), summary=proposal.get("summary", ""),
                   decision=decision, note=note, decided_by=decided_by)


def list_decisions(db, limit: int = 20) -> list[dict]:
    """Recent decisions, newest first — the audit trail shown in the UI."""
    rows = db.rows("approvals")
    return sorted(rows, key=lambda r: r["id"], reverse=True)[:limit]
