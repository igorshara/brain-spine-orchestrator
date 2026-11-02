"""Simulated controller link: a lost connection is unknown, never a confirmed OFF."""

import random

import pytest

from bso.patient_link import (ESCALATE_S, HEARTBEAT_S, LEAVE_ALERT_S, PAIR_S, REPEAT_S, SYNC_S,
                              TIMEOUT_S, InvalidEvents, program_id, replay)
from bso.stim_programs import PROGRAMS


def cmd(t, op, **kw):
    return {"t": t, "type": "cmd", "op": op, **kw}


def link(t, mode):
    return {"t": t, "type": "link", "mode": mode}


ON = [cmd(0, "on")]


def test_good_link_moves_from_requested_to_acknowledged():
    assert replay(ON, 0.1)["commands"][0]["state"] == "requested"
    state = replay(ON, 5)
    assert state["commands"][0]["state"] == "acknowledged"
    assert state["controller"]["state"] == "on" and state["implant_model"]["on"] is True


def test_ack_lost_after_delivery_is_unknown_while_implant_is_off():
    events = ON + [link(5, "lost_after"), cmd(6, "off")]
    state = replay(events, 6 + TIMEOUT_S + 1)
    assert state["commands"][-1]["state"] == "unknown"
    assert state["controller"]["state"] == "unknown"
    assert state["implant_model"]["on"] is False


def test_command_lost_before_delivery_is_unknown_while_implant_stays_on():
    events = ON + [link(5, "lost_before"), cmd(6, "off")]
    state = replay(events, 6 + TIMEOUT_S + 1)
    assert state["controller"]["state"] == "unknown"
    assert state["implant_model"]["on"] is True


def test_silent_link_never_renders_as_off():
    events = [link(1, "lost_before")]
    assert replay(events, 1 + HEARTBEAT_S + 1)["controller"]["state"] == "unknown"


def test_reconnect_reconciles_with_implant_and_marks_delivered_command_confirmed():
    restored = 20
    events = ON + [link(5, "lost_after"), cmd(6, "off"), link(restored, "good")]
    state = replay(events, restored + SYNC_S + 0.1)
    assert state["controller"]["state"] == "off"
    assert state["commands"][-1]["state"] == "acknowledged"
    assert state["commands"][-1]["reason"] == "confirmed_after_reconnect"


def test_reconnect_resends_only_off():
    restored = 20
    off = ON + [link(5, "lost_before"), cmd(6, "off"), link(restored, "good")]
    state = replay(off, restored + SYNC_S + 3)
    assert state["commands"][1]["state"] == "failed"
    assert state["commands"][2]["auto"] is True and state["commands"][2]["state"] == "acknowledged"
    assert state["implant_model"]["on"] is False

    up = ON + [link(5, "lost_before"), cmd(5.5, "amp_up"), link(restored, "good")]
    state = replay(up, restored + SYNC_S + 3)
    assert len(state["commands"]) == 2
    assert state["implant_model"]["amp"] == PROGRAMS[1].amp[0]


def test_status_query_leaves_a_command_sent_over_the_restored_link_alone():
    paired = 20 + PAIR_S
    events = ON + [{"t": 10, "type": "leave_home"}, {"t": 20, "type": "backup_pair"},
                   cmd(paired + SYNC_S - 0.3, "off")]
    state = replay(events, paired + 10)
    off = state["commands"][-1]
    assert (off["op"], off["state"], off["reason"]) == ("off", "acknowledged", None)
    assert state["controller"]["state"] == "off"
    assert state["implant_model"]["on"] is False


def test_second_press_of_off_while_one_is_on_its_way_adds_nothing():
    state = replay(ON + [cmd(5, "off"), cmd(5.3, "off")], 10)
    assert [c["op"] for c in state["commands"]] == ["on", "off"]
    assert state["controller"]["state"] == "off"
    later = replay(ON + [cmd(5, "off"), cmd(9, "off")], 12)
    assert len(later["commands"]) == 3


def test_only_off_is_allowed_while_state_is_unknown():
    events = ON + [link(5, "lost_before")]
    t = 5 + HEARTBEAT_S + 1
    for op in ("amp_up", "on"):
        state = replay(events + [cmd(t, op)], t + 0.1)
        assert state["commands"][-1]["state"] == "failed"
        assert state["commands"][-1]["reason"] == "state_unknown"
    state = replay(events + [cmd(t, "off")], t + 0.1)
    assert state["commands"][-1]["state"] == "requested"


def test_implant_refusal_is_failed_and_changes_nothing():
    state = replay(ON + [link(5, "refused"), cmd(6, "off")], 10)
    assert state["commands"][-1]["state"] == "failed"
    assert state["commands"][-1]["reason"] == "implant_refused"
    assert state["implant_model"]["on"] is True and state["controller"]["state"] == "on"


def test_amplitude_cannot_leave_the_range_the_clinician_set():
    index = 1
    lo, hi = PROGRAMS[index].amp
    events, t = list(ON), 3
    for _ in range(int((hi - lo) / 0.5) + 2):
        events.append(cmd(t, "amp_up"))
        t += 3
    state = replay(events, t)
    assert state["implant_model"]["amp"] == hi
    assert state["commands"][-1]["reason"] == "at_clinician_limit"


def test_every_program_passes_the_safety_supervisor_at_its_low_end():
    for index in range(len(PROGRAMS)):
        state = replay([cmd(0, "program", program=program_id(index))], 3)
        assert state["commands"][0]["state"] == "acknowledged", PROGRAMS[index]
        assert state["implant_model"]["amp"] == PROGRAMS[index].amp[0]


def test_repeated_commands_cool_down_and_are_never_silently_changed():
    events, t = list(ON), 3.0
    for i in range(120):
        events.append(cmd(t, "amp_up" if i % 2 == 0 else "amp_down"))
        t += 3
    state = replay(events, t)
    for command in state["commands"]:
        assert command["reason"] in (None, "safety_clamped", "safety_blocked")
        if command["reason"] == "safety_clamped":
            assert command["state"] == "acknowledged"


def test_left_behind_alert_then_backup_restores_control_but_not_amplitude():
    events = ON + [{"t": 5, "type": "leave_home"}]
    assert replay(events, 5 + LEAVE_ALERT_S - 1)["link"]["leave_alert"] is False
    state = replay(events, 5 + LEAVE_ALERT_S + 1)
    assert state["link"]["leave_alert"] is True and state["controller"]["state"] == "unknown"

    blocked = replay(events + [cmd(100, "off")], 101)
    assert blocked["commands"][-1]["reason"] == "no_controller"

    paired = events + [{"t": 100, "type": "backup_pair"}]
    ready = 100 + PAIR_S + SYNC_S + 1
    assert replay(paired, ready)["controller"]["state"] == "on"
    state = replay(paired + [cmd(ready, "amp_up")], ready + 2)
    assert state["commands"][-1]["reason"] == "backup_limited"
    state = replay(paired + [cmd(ready, "off")], ready + 2)
    assert state["controller"]["state"] == "off"


def start(t=2, minutes=60):
    return {"t": t, "type": "reminder_start", "minutes": minutes}


def test_reminder_counts_time_since_started_and_comes_due():
    events = ON + [start()]
    state = replay(events, 62)
    assert state["reminder"]["state"] == "running" and state["reminder"]["elapsed_s"] == 60
    assert replay(events, 2 + 3601)["reminder"]["state"] == "due"


def test_unanswered_reminder_repeats_then_escalates():
    due = 2 + 3600
    events = ON + [start()]
    state = replay(events, due + REPEAT_S + 1)
    assert state["reminder"]["notifications"] == 2 and not state["reminder"]["escalated"]
    assert replay(events, due + ESCALATE_S + 1)["reminder"]["escalated"] is True


def test_reminder_closes_only_after_off_is_confirmed():
    due = 2 + 3600
    events = ON + [start(), {"t": due + 1, "type": "reminder_ack", "choice": "off"}]
    state = replay(events, due + 3)
    assert state["reminder"]["state"] == "closed"
    assert state["reminder"]["outcome"] == "off_confirmed"
    assert state["implant_model"]["on"] is False


def test_reminder_stays_open_when_off_cannot_be_confirmed():
    due = 2 + 3600
    events = ON + [start(), link(due, "lost_after"),
                   {"t": due + 1, "type": "reminder_ack", "choice": "off"}]
    state = replay(events, due + 1 + TIMEOUT_S + 1)
    assert state["reminder"]["state"] == "off_unconfirmed"
    restored = due + 100
    state = replay(events + [link(restored, "good")], restored + SYNC_S + 1)
    assert state["reminder"]["outcome"] == "off_confirmed"


def test_snooze_and_keep_are_the_users_choice():
    due = 2 + 3600
    snooze = ON + [start(), {"t": due + 1, "type": "reminder_ack", "choice": "snooze"}]
    assert replay(snooze, due + 2)["reminder"]["state"] == "running"
    assert replay(snooze, due + 1 + 15 * 60 + 1)["reminder"]["state"] == "due"
    keep = ON + [start(), {"t": due + 1, "type": "reminder_ack", "choice": "keep"}]
    state = replay(keep, due + ESCALATE_S + 10)
    assert state["reminder"]["outcome"] == "kept_on" and not state["reminder"]["escalated"]
    assert state["implant_model"]["on"] is True


def test_auto_reminder_starts_when_on_is_acknowledged():
    events = [{"t": 0, "type": "settings", "auto_reminder_min": 30}, cmd(1, "on")]
    state = replay(events, 5)
    assert state["reminder"]["auto"] is True and state["reminder"]["minutes"] == 30


def test_controller_never_claims_a_state_the_implant_is_not_in():
    ops = ["on", "off", "amp_up", "amp_down"]
    modes = ["good", "refused", "lost_before", "lost_after"]
    for seed in range(200):
        rng = random.Random(seed)
        events, t = [], 0.0
        for _ in range(rng.randint(3, 25)):
            t += rng.uniform(0.1, 15)
            events.append(link(t, rng.choice(modes)) if rng.random() < 0.4
                          else cmd(t, rng.choice(ops)))
        for check_t in (t + 0.5, t + TIMEOUT_S + HEARTBEAT_S + 2):
            state = replay(events, check_t)
            known = state["controller"]["state"] != "unknown"
            if known and not state["controller"]["pending"]:
                believed_on = state["controller"]["state"] == "on"
                assert believed_on == state["implant_model"]["on"], (seed, check_t)


def test_replay_is_deterministic_and_rejects_bad_input():
    events = ON + [link(5, "lost_after"), cmd(6, "off")]
    assert replay(events, 30) == replay(events, 30)
    for bad, now in (([{"t": 1, "type": "nope"}], 2),
                     ([{"t": float("nan"), "type": "link", "mode": "good"}], 2),
                     ([cmd(1, "program", program="Z9:0")], 2),
                     ([cmd(1, "zap")], 2), ([], float("inf")), ("x", 1)):
        with pytest.raises(InvalidEvents):
            replay(bad, now)


def test_http_replay_returns_state_and_rejects_bad_input():
    import json
    import os
    import sys
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "web"))
    import server

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}"

    def post(body):
        req = urllib.request.Request(url + "/api/link/replay", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        return urllib.request.urlopen(req)

    try:
        state = json.load(post({"events": ON, "now": 5}))
        assert state["controller"]["state"] == "on"
        assert state["_meta"]["source"] == "illustrative"
        with pytest.raises(urllib.error.HTTPError) as err:
            post({"events": [{"t": 0, "type": "nope"}], "now": 1})
        assert err.value.code == 400
        for path, marker in (("/", b'id="app"'), ("/lab", b"data-tab"), ("/app/app.js", b"import")):
            assert marker in urllib.request.urlopen(url + path).read()
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(url + "/app/..%2Fserver.py")
    finally:
        httpd.shutdown()
