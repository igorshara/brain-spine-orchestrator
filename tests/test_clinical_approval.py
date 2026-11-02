"""Human-in-the-loop clinical approval: proposals are safety-checked, and every
clinician decision is logged to the recovery SSoT."""
import json
import os
import sys
import threading
import urllib.error
import urllib.request

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


def _post_decide(body: dict, tmp_path, monkeypatch) -> tuple[int, dict]:
    server_dir = os.path.join(os.path.dirname(__file__), "..", "web")
    sys.path.insert(0, server_dir)
    import server
    monkeypatch.setattr(server, "CLINIC_DB", str(tmp_path / "clinic.db"))
    srv = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{srv.server_port}/api/proposal/decide",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    finally:
        srv.shutdown()
        srv.server_close()


def test_omitted_decision_is_rejected_not_logged_as_approve(tmp_path, monkeypatch):
    code, body = _post_decide({"note": "no decision"}, tmp_path, monkeypatch)
    assert code == 400 and body["ok"] is False
    assert list_decisions(RecoveryDB(path=str(tmp_path / "clinic.db"))) == []


def test_explicit_decision_is_logged(tmp_path, monkeypatch):
    code, _ = _post_decide({"decision": "reject"}, tmp_path, monkeypatch)
    assert code == 200
    log = list_decisions(RecoveryDB(path=str(tmp_path / "clinic.db")))
    assert [row["decision"] for row in log] == ["reject"]
