"""Abstract biomechanical plant interface.

Контракт моделі тіла: приймає активації м'язових груп, повертає SensorFrame.
Swapping a kinematic toy for MuJoCo/OpenSim later must not touch other layers —
they only ever see this interface and the SensorFrame schema.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas import SensorFrame


class BioMechModel(ABC):
    """A simulated body driven by per-muscle-group activations."""

    @abstractmethod
    def step(self, activations: dict[str, float], t: float, dt: float) -> SensorFrame:
        """Advance the plant by ``dt`` under the given activations (0..1 per
        group_id) and return the resulting :class:`SensorFrame`."""

    @abstractmethod
    def reset(self) -> None:
        """Return the plant to its initial pose/state."""

    @abstractmethod
    def pose(self) -> dict[str, float]:
        """Return a render-friendly snapshot of the current pose."""
