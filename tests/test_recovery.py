"""Recovery SSoT + tracker + digest tests (deterministic core, no API key needed)."""

from __future__ import annotations

from bso.recovery import DOMAINS, RecoveryDB, weekly_digest


def _db():
    return RecoveryDB(":memory:")


def test_log_and_read_metrics():
    db = _db()
    db.log_metric("2026-05-01", "movement", 2.0)
    db.log_metric("2026-05-08", "movement", 3.0)
    assert len(db.rows("metrics")) == 2


def test_progress_detects_improvement():
    db = _db()
    for d, v in zip(["2026-04-01", "2026-04-08", "2026-04-15", "2026-04-22"],
                    [1.0, 1.0, 3.0, 3.5], strict=True):
        db.log_metric(d, "bladder", v)
    p = db.progress("bladder")
    assert p["trend"] == "improving" and p["delta"] > 0


def test_invalid_domain_rejected():
    db = _db()
    try:
        db.log_metric("2026-05-01", "telepathy", 5)
        raised = False
    except AssertionError:
        raised = True
    assert raised


def test_program_and_session_link():
    db = _db()
    pid = db.save_program("2026-05-11", "left knee flexion", 6, 5, 300, 40, 0.56)
    db.log_session("2026-05-11", "rehab+EES", 60, program_id=pid)
    s = db.rows("sessions")[0]
    assert s["program_id"] == pid


def test_weekly_digest_covers_all_domains_and_sections():
    db = _db()
    for d in DOMAINS:
        db.log_metric("2026-05-01", d, 2.0)
        db.log_metric("2026-05-08", d, 3.0)
    db.add_partner("Verita Neuro", "Bangkok", "meeting", "demo")
    db.add_task("prep demo")
    brief = weekly_digest(db)
    for d in DOMAINS:
        assert d in brief
    assert "Партнери" in brief and "Verita" in brief
    assert "задачі" in brief.lower()
