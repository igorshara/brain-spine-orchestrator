"""Deterministic tick-loop and a tiny synchronous message bus.

Детермінований tick-loop із фіксованим dt — старт обрано синхронним, бо так
найлегше тестувати й відтворювати. Components subscribe to topics and publish
messages; the loop ticks every component once per fixed timestep.

There is no wall-clock and no randomness here: time is the accumulated dt, so a
run is fully reproducible given the same components and seed.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any, Protocol


class Tickable(Protocol):
    """Anything the loop can drive once per timestep."""

    def tick(self, t: float, dt: float, bus: Bus) -> None: ...


class Bus:
    """Synchronous pub/sub used between layers within a tick.

    Messages published during a tick are delivered immediately to subscribers.
    The most recent message per topic is also retained so late subscribers (and
    tests) can read current state via :meth:`latest`.
    """

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[Any], None]]] = defaultdict(list)
        self._latest: dict[str, Any] = {}
        self.log: list[tuple[float, str, Any]] = []
        self._record = False
        self._t = 0.0

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        self._subs[topic].append(handler)

    def publish(self, topic: str, message: Any) -> None:
        self._latest[topic] = message
        if self._record:
            self.log.append((self._t, topic, message))
        for handler in self._subs[topic]:
            handler(message)

    def latest(self, topic: str, default: Any = None) -> Any:
        return self._latest.get(topic, default)

    # internal: set by the loop so publish() can timestamp the log
    def _set_time(self, t: float) -> None:
        self._t = t

    def enable_recording(self, on: bool = True) -> None:
        self._record = on


class TickLoop:
    """Fixed-dt driver. Ticks each registered component in registration order."""

    def __init__(self, dt: float = 0.005, bus: Bus | None = None) -> None:
        if dt <= 0:
            raise ValueError("dt must be positive")
        self.dt = dt
        self.bus = bus or Bus()
        self.components: list[Tickable] = []
        self.t = 0.0
        self.step_count = 0

    def add(self, component: Tickable) -> Tickable:
        self.components.append(component)
        return component

    def step(self) -> None:
        self.bus._set_time(self.t)
        for c in self.components:
            c.tick(self.t, self.dt, self.bus)
        self.t += self.dt
        self.step_count += 1

    def run(self, duration_s: float) -> None:
        n = int(round(duration_s / self.dt))
        for _ in range(n):
            self.step()

    def run_steps(self, n: int) -> None:
        for _ in range(n):
            self.step()
