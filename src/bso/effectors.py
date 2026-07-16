"""Layer 2 — Effectors (one mapper per muscle group / electrode zone).

Шар 2 — ефекторні агенти. Кожен мапить desired_activation своєї групи в
параметри стимуляції конкретних контактів (амплітуда, ширина імпульсу, частота)
через ІНВЕРСНУ криву рекрутингу. Вихід — StimCommand, що ОБОВ'ЯЗКОВО проходить
через Шар 5 (safety) перед застосуванням.

Deterministic mapper + calibration curve (canon §3, Layer 2). Parameters come
from config/muscles.py.
"""

from __future__ import annotations

from .bus import Bus
from .config.muscles import MUSCLE_GROUPS
from .schemas import MuscleTarget, StimCommand


class Effectors:
    """Converts the orchestrator's MuscleTarget stream into StimCommands.

    Topics: in ``muscle_targets`` -> out ``stim_commands`` (a list of raw,
    pre-safety commands; the runtime routes each through the safety supervisor).
    """

    IN_TARGETS = "muscle_targets"
    OUT_COMMANDS = "stim_commands"

    def __init__(self) -> None:
        self.groups = MUSCLE_GROUPS
        # Per-group amplitude gain (default 1.0). The slow adaptation layer
        # (Layer 4) tunes these to compensate for fatigue/drift. Safety still
        # clamps the result — gains can never push past the hard envelope.
        self.gains: dict[str, float] = dict.fromkeys(MUSCLE_GROUPS, 1.0)

    def map_target(self, mt: MuscleTarget) -> StimCommand | None:
        g = self.groups.get(mt.group_id)
        if g is None:
            return None
        amplitude = g.recruitment.amplitude_for(mt.desired_activation)
        amplitude *= self.gains.get(mt.group_id, 1.0)
        return StimCommand(
            t=mt.t,
            channel_id=g.channel_id,
            amplitude_mA=amplitude,
            pulse_width_us=g.default_pulse_width_us,
            frequency_Hz=g.default_frequency_Hz,
            active_contacts=g.contacts,
        )

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        targets: list[MuscleTarget] | None = bus.latest(self.IN_TARGETS)
        if not targets:
            return
        commands = [c for mt in targets if (c := self.map_target(mt)) is not None]
        bus.publish(self.OUT_COMMANDS, commands)
