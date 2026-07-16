"""Unified substrate — one organism, not three engines.

The partner brief promises "one substrate" for locomotion AND autonomic function.
This module makes that literally true in code: locomotion (decoder → orchestrator →
effectors → spinal cord → body → feedback) and the autonomic loop (bladder/bowel/
erectile) are wired onto a SINGLE Bus, a SINGLE TickLoop and a SINGLE
SafetySupervisor, and ticked together. Every command from either loop passes through
the same safety gate in the same tick — not two systems that merely look alike.

The two loops use disjoint bus topics (autonomic topics are `auto_*`-prefixed), so
they coexist on one bus without collision.

Illustrative research simulation — not a medical device.
"""
from __future__ import annotations

from dataclasses import dataclass

from .autonomic import IntegratedAutonomicSystem, build_autonomic_system
from .bus import Bus, TickLoop
from .runtime import System, build_system
from .safety import SafetySupervisor


@dataclass
class UnifiedSystem:
    """Locomotion + autonomic on one shared substrate."""

    loop: TickLoop
    bus: Bus
    safety: SafetySupervisor
    locomotion: System
    autonomic: IntegratedAutonomicSystem

    def run(self, duration_s: float):
        """Tick both loops together. Returns (locomotion recorder, autonomic system)."""
        self.loop.run(duration_s)
        return self.locomotion.recorder, self.autonomic

    def evidence(self) -> dict:
        """Machine-checkable proof that this is one substrate, not three engines."""
        return {
            "one_bus": self.locomotion.bus is self.autonomic.bus is self.bus,
            "one_tick_loop": self.locomotion.loop is self.autonomic.loop is self.loop,
            "one_safety_gate": self.locomotion.safety is self.autonomic.safety is self.safety,
        }


def build_unified_system(loco_schedule, auto_schedule, *, dt: float = 0.01,
                         modulation: bool = True, dyssynergia: bool = True,
                         **loco_kw) -> UnifiedSystem:
    """Build locomotion and autonomic on ONE bus / loop / safety gate."""
    bus = Bus()
    bus.enable_recording(False)
    safety = SafetySupervisor()
    loop = TickLoop(dt=dt, bus=bus)
    loco = build_system(loco_schedule, dt=dt, safety=safety, bus=bus, loop=loop, **loco_kw)
    auton = build_autonomic_system(auto_schedule, dt=dt, modulation=modulation,
                                   dyssynergia=dyssynergia, safety=safety, bus=bus, loop=loop)
    return UnifiedSystem(loop=loop, bus=bus, safety=safety, locomotion=loco, autonomic=auton)
