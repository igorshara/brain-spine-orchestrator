"""Simulated patient controller link: what a controller knows versus what an implant does.

Pure, deterministic replay of a client-held event log. No state lives on the server and
nothing here talks to hardware: the implant is a model. The central rule is that a lost
connection yields "unknown", never a confirmed OFF. All timings are ILLUSTRATIVE.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

from bso.safety import SafetySupervisor
from bso.schemas import StimCommand
from bso.stim_programs import PROGRAMS

DELIVER_S = 0.6       # ILLUSTRATIVE command reaches the implant
ACK_S = 1.2           # ILLUSTRATIVE acknowledgement reaches the controller
TIMEOUT_S = 8.0       # ILLUSTRATIVE no acknowledgement: outcome is unknown
HEARTBEAT_S = 10.0    # ILLUSTRATIVE silent link: state is unknown
SYNC_S = 1.5          # ILLUSTRATIVE status query after the link returns
LEAVE_ALERT_S = 60.0  # ILLUSTRATIVE communicator left behind: alert the phone
PAIR_S = 20.0         # ILLUSTRATIVE pairing a pre-authorized backup controller
AMP_STEP = 0.5        # ILLUSTRATIVE patient amplitude step
REPEAT_S = 5 * 60.0   # ILLUSTRATIVE repeat an unanswered reminder
ESCALATE_S = 15 * 60.0  # ILLUSTRATIVE tell the trusted person
SNOOZE_S = 15 * 60.0  # ILLUSTRATIVE
MAX_EVENTS = 500

LINK_MODES = ("good", "refused", "lost_before", "lost_after")
COMMAND_OPS = ("on", "off", "program", "amp_up", "amp_down")
USER_EVENTS = ("cmd", "link", "leave_home", "go_back", "backup_pair", "settings",
               "reminder_start", "reminder_ack")
REMINDER_CHOICES = ("off", "snooze", "keep")


class InvalidEvents(ValueError):
    """The event log cannot be replayed."""


def program_id(index: int) -> str:
    return f"{PROGRAMS[index].slot}:{index}"


def _program_index(pid) -> int | None:
    if not isinstance(pid, str) or ":" not in pid:
        return None
    try:
        index = int(pid.rsplit(":", 1)[1])
    except ValueError:
        return None
    if 0 <= index < len(PROGRAMS) and program_id(index) == pid:
        return index
    return None


def _number(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def validate_events(events, now) -> None:
    if not _number(now) or now < 0:
        raise InvalidEvents("now must be a finite non-negative number")
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise InvalidEvents(f"events must be a list of at most {MAX_EVENTS}")
    for event in events:
        if not isinstance(event, dict) or event.get("type") not in USER_EVENTS:
            raise InvalidEvents("unknown event type")
        if not _number(event.get("t")) or event["t"] < 0:
            raise InvalidEvents("event time must be a finite non-negative number")
        kind = event["type"]
        if kind == "cmd":
            if event.get("op") not in COMMAND_OPS:
                raise InvalidEvents("unknown command")
            if event["op"] == "program" and _program_index(event.get("program")) is None:
                raise InvalidEvents("unknown program")
        elif kind == "link" and event.get("mode") not in LINK_MODES:
            raise InvalidEvents("unknown link mode")
        elif kind == "reminder_start" and not (_number(event.get("minutes"))
                                               and 0 < event["minutes"] <= 24 * 60):
            raise InvalidEvents("reminder minutes out of range")
        elif kind == "reminder_ack" and event.get("choice") not in REMINDER_CHOICES:
            raise InvalidEvents("unknown reminder choice")
        elif kind == "settings":
            minutes = event.get("auto_reminder_min")
            if minutes is not None and not (_number(minutes) and 0 < minutes <= 24 * 60):
                raise InvalidEvents("auto reminder minutes out of range")


@dataclass
class _Command:
    id: int
    op: str
    t: float
    state: str = "requested"
    program: str | None = None
    amp: float | None = None
    resolved_t: float | None = None
    reason: str | None = None
    delivered: bool = False
    auto: bool = False
    epoch: int = 0

    def view(self) -> dict:
        return {"id": self.id, "op": self.op, "t": self.t, "state": self.state,
                "program": self.program, "amp": self.amp, "resolved_t": self.resolved_t,
                "reason": self.reason, "auto": self.auto}


@dataclass
class _Sim:
    now: float
    t: float = 0.0
    seq: int = 0
    queue: list = field(default_factory=list)
    mode: str = "good"
    primary_present: bool = True
    backup_state: str = "none"      # none / pairing / active
    leave_alert: bool = False
    truth_on: bool = False
    truth_program: int = 1          # A2, the owner's highest-rate walking slot
    truth_amp: float = PROGRAMS[1].amp[0]
    on_since: float | None = None
    belief: str = "off"             # on / off / unknown
    belief_program: int = 1
    belief_amp: float = PROGRAMS[1].amp[0]
    confirmed_t: float = 0.0
    unknown_since: float | None = None
    commands: list = field(default_factory=list)
    log: list = field(default_factory=list)
    timeline: list = field(default_factory=list)
    auto_reminder_min: float | None = None
    reminder: dict | None = None
    reminder_epoch: int = 0
    link_epoch: int = 0
    safety: SafetySupervisor = field(default_factory=SafetySupervisor)
    _clamped: bool = False
    _last_safety_t: float = 0.0

    # ------------------------------------------------------------------ plumbing
    def at(self, t: float, kind: str, **payload) -> None:
        self.seq += 1
        heapq.heappush(self.queue, (t, self.seq, kind, payload))

    def note(self, key: str, **params) -> None:
        self.log.append({"t": self.t, "key": key, **params})

    @property
    def controller_available(self) -> bool:
        return self.primary_present or self.backup_state == "active"

    @property
    def link_up(self) -> bool:
        return self.controller_available and self.mode in ("good", "refused")

    def _confirm(self) -> None:
        self.belief = "on" if self.truth_on else "off"
        self.belief_program = self.truth_program
        self.belief_amp = self.truth_amp
        self.confirmed_t = self.t
        self.unknown_since = None
        self._settle_reminder()

    def _make_unknown(self) -> None:
        if self.belief != "unknown":
            self.belief = "unknown"
            self.unknown_since = self.t
            self.note("state_unknown")
        self._settle_reminder()

    def _pending(self) -> bool:
        return any(c.state == "requested" for c in self.commands)

    # ------------------------------------------------------------------ commands
    def _fail(self, cmd: _Command, reason: str) -> None:
        cmd.state, cmd.reason, cmd.resolved_t = "failed", reason, self.t
        self.note("command_failed", op=cmd.op, reason=reason)
        self._settle_reminder()

    def send(self, op: str, program: str | None = None, auto: bool = False) -> _Command:
        cmd = _Command(id=len(self.commands) + 1, op=op, t=self.t, program=program, auto=auto,
                       epoch=self.link_epoch)
        reason = self._local_refusal(cmd)
        self.commands.append(cmd)
        self.note("command_requested", op=op, auto=auto, program=program)
        if reason:
            self._fail(cmd, reason)
            return cmd
        if self.mode == "refused":
            self.at(self.t + ACK_S, "refuse", cmd=cmd)
            return cmd
        if self.mode != "lost_before" and self.controller_available:
            self.at(self.t + DELIVER_S, "deliver", cmd=cmd)
        if self.link_up:
            self.at(self.t + ACK_S, "ack", cmd=cmd)
        else:
            self.at(self.t + TIMEOUT_S, "timeout", cmd=cmd)
        return cmd

    def _local_refusal(self, cmd: _Command) -> str | None:
        """Checks a controller can make without talking to the implant."""
        if not self.controller_available:
            return "no_controller"
        if cmd.op == "off":
            return None                 # always allowed, even when the state is unknown
        if self.backup_state == "active" and not self.primary_present:
            return "backup_limited"     # the backup can only switch off
        if self.belief == "unknown":
            return "state_unknown"
        if self._pending():
            return "command_pending"
        if cmd.op == "on" and self.belief == "on":
            return "already_on"
        if cmd.op in ("amp_up", "amp_down"):
            if self.belief != "on":
                return "not_on"
            lo, hi = PROGRAMS[self.belief_program].amp
            target = self.belief_amp + (AMP_STEP if cmd.op == "amp_up" else -AMP_STEP)
            if target > hi or target < lo:
                return "at_clinician_limit"
            cmd.amp = target
        return None

    def _deliver(self, cmd: _Command) -> None:
        if cmd.delivered or self.mode == "lost_before":
            return
        verdict = self._safety_check(cmd)
        if verdict is None:
            cmd.reason = "safety_blocked"
            return
        cmd.delivered = True
        if self._clamped:
            cmd.reason = "safety_clamped"
        if cmd.op == "on":
            if not self.truth_on:
                self.on_since = self.t
            self.truth_on = True
        elif cmd.op == "off":
            self.truth_on = False
            self.on_since = None
        elif cmd.op == "program":
            self.truth_program = _program_index(cmd.program)
            self.truth_amp = PROGRAMS[self.truth_program].amp[0]
        elif cmd.op in ("amp_up", "amp_down"):
            self.truth_amp = verdict

    def _safety_check(self, cmd: _Command) -> float | None:
        """Every command passes the supervisor; returns the applied amplitude or None."""
        index = _program_index(cmd.program) if cmd.op == "program" else self.truth_program
        program = PROGRAMS[index]
        self.safety.tick(self.t, max(0.0, self.t - self._last_safety_t))
        self._last_safety_t = self.t
        amp = cmd.amp if cmd.amp is not None else (
            program.amp[0] if cmd.op == "program" else self.truth_amp)
        verdict = self.safety.check(StimCommand(
            t=self.t, channel_id="patient_link", amplitude_mA=amp,
            pulse_width_us=program.mid()["pw_us"], frequency_Hz=program.mid()["rate_hz"],
            active_contacts=(1,)))
        self._clamped = verdict.clamped
        return verdict.command.amplitude_mA if verdict.approved else None

    def _on_ack(self, cmd: _Command) -> None:
        if cmd.state != "requested":
            return
        if not self.link_up:
            self.at(max(self.t, cmd.t + TIMEOUT_S), "timeout", cmd=cmd)
            return
        if not cmd.delivered:
            self._deliver(cmd)
        if not cmd.delivered:
            self._fail(cmd, cmd.reason or "not_delivered")
            return
        cmd.state, cmd.resolved_t = "acknowledged", self.t
        self.note("command_acknowledged", op=cmd.op)
        self._confirm()
        if cmd.op == "on" and self.auto_reminder_min and not self._reminder_open():
            self._start_reminder(self.auto_reminder_min, auto=True)

    def _on_timeout(self, cmd: _Command) -> None:
        if cmd.state == "requested":
            cmd.state, cmd.resolved_t = "unknown", self.t
            self.note("command_unknown", op=cmd.op)
            self._make_unknown()

    # ------------------------------------------------------------------ link
    def _link_changed(self) -> None:
        self.link_epoch += 1
        if self.link_up:
            self.at(self.t + SYNC_S, "sync", epoch=self.link_epoch)
        else:
            self.at(self.t + HEARTBEAT_S, "heartbeat", epoch=self.link_epoch)

    def _sync(self) -> None:
        """Status query after a reconnect. Only OFF is resent; other commands never are."""
        for cmd in self.commands:
            # A command sent over the restored link is still on its way and resolves by itself.
            if cmd.state in ("requested", "unknown") and cmd.epoch < self.link_epoch:
                cmd.resolved_t = self.t
                if cmd.delivered:
                    cmd.state = "acknowledged"
                    cmd.reason = "confirmed_after_reconnect"
                else:
                    cmd.state, cmd.reason = "failed", "not_delivered"
        self.note("state_confirmed", on=self.truth_on)
        self._confirm()
        latest = self.commands[-1] if self.commands else None
        if latest and latest.op == "off" and latest.state == "failed" and self.truth_on:
            self.send("off", auto=True)

    # ------------------------------------------------------------------ reminder
    def _reminder_open(self) -> bool:
        return bool(self.reminder) and self.reminder["state"] != "closed"

    def _start_reminder(self, minutes: float, auto: bool = False) -> None:
        self.reminder_epoch += 1
        self.reminder = {"state": "running", "started_t": self.t, "minutes": minutes,
                         "due_t": self.t + minutes * 60.0, "notifications": 0,
                         "escalated": False, "outcome": None, "auto": auto,
                         "closed_t": None}
        self.note("reminder_started", minutes=minutes, auto=auto)
        self._arm_reminder()

    def _arm_reminder(self) -> None:
        due = self.reminder["due_t"]
        epoch = self.reminder_epoch
        self.at(due, "due", epoch=epoch)
        self.at(due + REPEAT_S, "repeat", epoch=epoch)
        self.at(due + ESCALATE_S, "escalate", epoch=epoch)

    def _close_reminder(self, outcome: str) -> None:
        self.reminder_epoch += 1
        self.reminder.update(state="closed", outcome=outcome, closed_t=self.t)
        self.note("reminder_closed", outcome=outcome)

    def _settle_reminder(self) -> None:
        """Keep an off request open until the controller has confirmed OFF."""
        rem = self.reminder
        if not rem or rem["state"] not in ("off_requested", "off_unconfirmed", "off_failed"):
            return
        if self.belief == "off":
            self._close_reminder("off_confirmed")
        elif self.belief == "unknown":
            rem["state"] = "off_unconfirmed"
        elif self.commands and self.commands[-1].state == "failed":
            rem["state"] = "off_failed"

    def _reminder_ack(self, choice: str) -> None:
        if not self._reminder_open():
            return
        self.reminder_epoch += 1
        if choice == "keep":
            self._close_reminder("kept_on")
        elif choice == "snooze":
            self.reminder.update(state="running", due_t=self.t + SNOOZE_S, notifications=0)
            self.note("reminder_snoozed")
            self._arm_reminder()
        else:
            self.reminder["state"] = "off_requested"
            self.send("off")

    # ------------------------------------------------------------------ dispatcher
    def handle_user(self, event: dict) -> None:
        kind = event["type"]
        if kind == "cmd":
            # A second press of Switch off while one is on its way adds nothing.
            if event["op"] == "off" and any(c.op == "off" and c.state == "requested" for c in self.commands):
                return
            self.send(event["op"], event.get("program"))
        elif kind == "link":
            self.mode = event["mode"]
            self.note("link_changed", mode=self.mode)
            self._link_changed()
        elif kind == "leave_home":
            self.primary_present = False
            self.note("left_behind")
            self.at(self.t + LEAVE_ALERT_S, "leave_alert")
            self._link_changed()
        elif kind == "go_back":
            self.primary_present = True
            self.leave_alert = False
            self.note("controller_back")
            self._link_changed()
        elif kind == "backup_pair":
            if self.backup_state == "none":
                self.backup_state = "pairing"
                self.note("backup_pairing")
                self.at(self.t + PAIR_S, "paired")
        elif kind == "settings":
            self.auto_reminder_min = event.get("auto_reminder_min")
        elif kind == "reminder_start":
            self._start_reminder(event["minutes"])
        elif kind == "reminder_ack":
            self._reminder_ack(event["choice"])

    def handle_internal(self, kind: str, p: dict) -> None:
        if kind == "user":
            self.handle_user(p["event"])
        elif kind == "deliver":
            self._deliver(p["cmd"])
        elif kind == "ack":
            self._on_ack(p["cmd"])
        elif kind == "timeout":
            self._on_timeout(p["cmd"])
        elif kind == "refuse":
            if p["cmd"].state == "requested":
                self._fail(p["cmd"], "implant_refused")
        elif kind == "sync":
            if p["epoch"] == self.link_epoch and self.link_up:
                self._sync()
        elif kind == "heartbeat":
            if p["epoch"] == self.link_epoch and not self.link_up:
                self._make_unknown()
        elif kind == "leave_alert":
            if not self.primary_present:
                self.leave_alert = True
                self.note("left_behind_alert")
        elif kind == "paired":
            self.backup_state = "active"
            self.note("backup_active")
            self._link_changed()
        elif p.get("epoch") == self.reminder_epoch and self._reminder_open():
            if kind == "due":
                self.reminder.update(state="due", notifications=1)
                self.note("reminder_due")
            elif kind == "repeat":
                self.reminder["notifications"] += 1
                self.note("reminder_repeated")
            elif kind == "escalate":
                self.reminder["escalated"] = True
                self.note("reminder_escalated")

    def _mark(self) -> None:
        """Record a timeline row whenever what the controller says or the implant does changes."""
        row = {"controller": self.belief, "pending": self._pending(),
               "implant_on": self.truth_on, "link_up": self.link_up}
        if self.timeline and self.timeline[-1]["t"] == self.t:
            self.timeline[-1].update(row)
        elif not self.timeline or any(self.timeline[-1][k] != v for k, v in row.items()):
            self.timeline.append({"t": self.t, **row})

    def run(self) -> float | None:
        self._mark()
        while self.queue and self.queue[0][0] <= self.now:
            self.t, _, kind, payload = heapq.heappop(self.queue)
            self.handle_internal(kind, payload)
            self._mark()
        self.t = self.now
        return self.queue[0][0] if self.queue else None


def _disagrees(row: dict) -> bool:
    """The screen does not match the implant: a state is unknown, or a settled state is wrong."""
    return row["controller"] == "unknown" or (row["controller"] == "on") != row["implant_on"]


def disagreement_seconds(timeline: list, now: float) -> float:
    ends = [row["t"] for row in timeline[1:]] + [now]
    return sum(end - row["t"] for row, end in zip(timeline, ends) if _disagrees(row))


def replay(events: list, now: float) -> dict:
    """Derive the full simulated state at time `now` from an event log."""
    validate_events(events, now)
    sim = _Sim(now=now)
    for event in sorted(events, key=lambda e: e["t"]):
        if event["t"] <= now:
            sim.at(event["t"], "user", event=event)
    next_change = sim.run()

    rem = sim.reminder
    reminder = dict(rem) if rem else None
    if reminder:
        end = reminder["closed_t"] if reminder["closed_t"] is not None else now
        reminder["elapsed_s"] = max(0.0, end - reminder["started_t"])
    return {
        "now": now,
        "next_change_t": next_change,
        "controller": {
            "state": sim.belief,
            "program": program_id(sim.belief_program),
            "amp": sim.belief_amp,
            "amp_range": list(PROGRAMS[sim.belief_program].amp),
            "last_confirmed_t": sim.confirmed_t,
            "unknown_since": sim.unknown_since,
            "pending": sim._pending(),
        },
        "implant_model": {
            "on": sim.truth_on,
            "program": program_id(sim.truth_program),
            "amp": sim.truth_amp,
            "on_for_s": (now - sim.on_since) if sim.on_since is not None else None,
        },
        "link": {
            "mode": sim.mode,
            "up": sim.link_up,
            "primary_present": sim.primary_present,
            "backup": sim.backup_state,
            "leave_alert": sim.leave_alert,
        },
        "commands": [c.view() for c in sim.commands],
        "reminder": reminder,
        "auto_reminder_min": sim.auto_reminder_min,
        "log": sim.log,
        "timeline": sim.timeline,
        "disagreement_s": disagreement_seconds(sim.timeline, now),
    }
