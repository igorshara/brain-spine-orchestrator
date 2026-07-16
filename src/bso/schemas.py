"""Message contracts between agents/layers.

Контракти повідомлень між шарами. Усі числові межі — ILLUSTRATIVE.
These dataclasses are the *only* sanctioned way data crosses layer boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Mode(Enum):
    """High-level volitional intent decoded from the brain (Layer 0)."""

    IDLE = "idle"
    SIT = "sit"
    STAND = "stand"
    WALK = "walk"
    TURN_L = "turn_left"
    TURN_R = "turn_right"
    STAIRS_UP = "stairs_up"
    STAIRS_DOWN = "stairs_down"


class Phase(Enum):
    """Gait cycle phase per leg."""

    STANCE = "stance"
    SWING = "swing"
    DOUBLE_SUPPORT = "double_support"


class Side(Enum):
    LEFT = "L"
    RIGHT = "R"


@dataclass
class Intent:
    """Layer 0 -> Layer 1. Decoded volitional intent. The decoder only *reads*
    intent; it never decides to move on the patient's behalf."""

    t: float  # s
    mode: Mode
    speed: float  # 0..1, desired locomotion speed
    confidence: float  # 0..1, decoder confidence


@dataclass
class GaitState:
    """Layer 3 -> Layer 1. Estimated state of the body from sensor fusion."""

    t: float
    phase_left: Phase
    phase_right: Phase
    cycle_phase: float  # 0..1 within the gait cycle
    cadence: float  # steps/min
    balance_ok: bool
    trunk_tilt_deg: float = 0.0  # forward(+)/back(-) lean estimate


@dataclass
class MuscleTarget:
    """Layer 1 -> Layer 2. Desired activation for one muscle group with the
    phase window in which it should be active."""

    t: float
    group_id: str  # e.g. "L_hip_flex"
    desired_activation: float  # 0..1
    phase_window: tuple[float, float]  # (start, end) in cycle_phase


@dataclass
class StimCommand:
    """Layer 2 -> Layer 5 -> stimulator model. ALL numeric fields ILLUSTRATIVE.
    Must pass through the safety supervisor before it can be applied."""

    t: float
    channel_id: str
    amplitude_mA: float  # ILLUSTRATIVE
    pulse_width_us: float  # ILLUSTRATIVE
    frequency_Hz: float  # ILLUSTRATIVE
    active_contacts: tuple[int, ...] = ()

    @property
    def charge_per_phase_uC(self) -> float:
        """Q = I * PW. Charge per phase in microcoulombs (mA * us = nC; /1000 -> uC)."""
        return self.amplitude_mA * self.pulse_width_us / 1000.0


@dataclass
class SensorFrame:
    """BioMech model -> Layer 3. Simulated sensors."""

    t: float
    imu: dict[str, float] = field(default_factory=dict)  # accel/gyro per segment
    joint_angles: dict[str, float] = field(default_factory=dict)  # hip/knee/ankle L/R, deg
    grf: dict[str, float] = field(default_factory=dict)  # L/R ground reaction force, N
    emg: dict[str, float] = field(default_factory=dict)  # synthetic EMG per group, 0..1


@dataclass
class SafetyVerdict:
    """Layer 5 output. Absolute veto authority over every StimCommand."""

    approved: bool
    clamped: bool
    reason: str
    command: StimCommand  # safe (possibly clamped) command


@dataclass
class AdaptationUpdate:
    """Layer 4 -> Layers 1-2. Slow, between-session parameter deltas."""

    t: float
    target_id: str
    param_deltas: dict[str, float]
    rationale: str
