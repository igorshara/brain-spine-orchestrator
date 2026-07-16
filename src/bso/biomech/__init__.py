"""Biomechanical plant models. Abstract interface + a simple kinematic start.

Біомеханіка абстрагована за інтерфейсом BioMechModel, щоб згодом підставити
MuJoCo/OpenSim без зміни решти системи.
"""

from .base import BioMechModel
from .kinematic import KinematicModel

__all__ = ["BioMechModel", "KinematicModel"]
