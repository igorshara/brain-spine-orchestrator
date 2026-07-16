"""Human-in-the-loop clinical approval: proposals are safety-checked, and every
clinician decision is logged to the recovery SSoT."""
from bso.clinical_approval import (N_PROPOSALS, build_proposal, list_decisions,
                                   log_decision)
from bso.recovery import RecoveryDB


def test_proposals_are_within_safety_envelope():
    # Every illustrative proposal must be safe-by-construction (clinician is never
    # shown an out-of-envelope suggestion).
    for i in range(N_PROPOSALS):
        p = build_proposal(i)
        assert p["safe"] is True, p
        assert p["charge_uC"] > 0
        assert p["id"]


def test_bilingual_proposal():
    assert build_proposal(0, "en")["safety_note"] == "within safety envelope"
    assert build_proposal(0, "ua")["safety_note"] == "у межах безпеки"


def test_decision_is_logged_and_listed():
    db = RecoveryDB(path=":memory:")
    p = build_proposal(0)
    log_decision(db, "2026-06-27 10:00:00", p, "approve", note="looks good")
    log_decision(db, "2026-06-27 10:01:00", p, "reject", note="too aggressive")
    log = list_decisions(db)
    assert len(log) == 2
    assert log[0]["decision"] == "reject"     # newest first
    assert log[1]["decision"] == "approve"
    assert log[0]["target"] == p["target"]


def test_nothing_applied_without_decision():
    # An empty log means no change was ever applied — the default state.
    db = RecoveryDB(path=":memory:")
    assert list_decisions(db) == []
