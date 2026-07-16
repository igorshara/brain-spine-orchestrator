"""Layer 0 — Decoder stub (intent source).

Шар 0 — заглушка декодера наміру. У реалі це кортикальний декодер; тут — джерело
наміру з заданого сценарію. КРИТИЧНО (канон §1.2): декодер лише ЧИТАЄ намір,
він ніколи не «вирішує рухатись» за людину.

A scenario is a time-ordered list of (t_start, Intent-without-time). The stub
publishes the active intent on the ``intent`` topic each tick.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .bus import Bus
from .schemas import Intent, Mode


@dataclass
class IntentEvent:
    t_start: float
    mode: Mode
    speed: float = 0.0
    confidence: float = 1.0


class DecoderStub:
    """Replays a scripted sequence of intents. Topic: ``intent``."""

    TOPIC = "intent"

    def __init__(self, schedule: Sequence[IntentEvent]) -> None:
        self.schedule = sorted(schedule, key=lambda e: e.t_start)
        self._idx = -1

    def current_event(self, t: float) -> IntentEvent:
        ev = self.schedule[0] if self.schedule else IntentEvent(0.0, Mode.IDLE)
        for e in self.schedule:
            if e.t_start <= t:
                ev = e
            else:
                break
        return ev

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        ev = self.current_event(t)
        intent = Intent(t=t, mode=ev.mode, speed=ev.speed, confidence=ev.confidence)
        bus.publish(self.TOPIC, intent)
