"""Simple kinematic lower-limb model (canon M2 start).

Спрощена кінематична модель нижніх кінцівок. Кожен суглоб керується НЕТТО-
активацією антагоністичної пари м'язів через пружинно-демпферний привід:

    net      = activation(flexor) - activation(extensor)        # -1..1
    target   = neutral + range * net
    a        = stiffness * (target - angle) - damping * vel
    vel     += a * dt ;  angle += vel * dt ;  angle clamped to ROM

Це навмисне спрощення (документоване в каноні §2): EES насправді рекрутує
аференти й вмикає спінальні контури, ми ж моделюємо ЕФЕКТ через активацію.
The model produces plausible joint angles, ground reaction forces and a
synthetic IMU/EMG so the closed loop has something to fuse.

All geometry numbers are ILLUSTRATIVE (rough adult lower-limb proportions).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..muscle import HillMuscle
from ..schemas import SensorFrame
from .base import BioMechModel

# Muscle groups per joint (agonist, antagonist) for the optional Hill-muscle mode.
_JOINT_MUSCLES = {
    "hip": ("hip_flex", "hip_ext"),
    "knee": ("knee_flex", "knee_ext"),
    "ankle": ("ankle_dorsi", "ankle_plantar"),
}

# --- ILLUSTRATIVE segment geometry (metres) ---
HIP_HEIGHT = 0.92  # standing hip height
THIGH_LEN = 0.45
SHANK_LEN = 0.45
FOOT_LEN = 0.25
BODY_WEIGHT_N = 750.0  # ~76 kg


@dataclass
class _Joint:
    angle: float  # deg (flexion positive)
    vel: float = 0.0
    neutral: float = 0.0
    rom: tuple[float, float] = (-10.0, 90.0)
    range_deg: float = 45.0  # how far full net activation drives it
    stiffness: float = 900.0  # spring toward target (1/s^2)
    damping: float = 60.0  # velocity damping (1/s)

    def integrate(self, net: float, dt: float) -> None:
        target = self.neutral + self.range_deg * net
        a = self.stiffness * (target - self.angle) - self.damping * self.vel
        self.vel += a * dt
        self.angle += self.vel * dt
        lo, hi = self.rom
        if self.angle < lo:
            self.angle, self.vel = lo, 0.0
        elif self.angle > hi:
            self.angle, self.vel = hi, 0.0


@dataclass
class KinematicModel(BioMechModel):
    """Two legs (hip/knee/ankle each) + a trunk lean state."""

    joints: dict[str, _Joint] = field(default_factory=dict)
    trunk_tilt: float = 0.0  # deg, forward positive
    trunk_vel: float = 0.0
    use_muscles: bool = False  # opt-in Hill-type muscle dynamics (activation + FL/FV)
    _emg: dict[str, float] = field(default_factory=dict)
    _prev_angles: dict[str, float] = field(default_factory=dict)
    _muscles: dict[str, HillMuscle] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.joints:
            self.reset()

    def reset(self) -> None:
        self.joints = {
            "L_hip": _Joint(angle=0.0, neutral=0.0, rom=(-20.0, 100.0), range_deg=40.0),
            "R_hip": _Joint(angle=0.0, neutral=0.0, rom=(-20.0, 100.0), range_deg=40.0),
            "L_knee": _Joint(angle=5.0, neutral=5.0, rom=(0.0, 130.0), range_deg=55.0),
            "R_knee": _Joint(angle=5.0, neutral=5.0, rom=(0.0, 130.0), range_deg=55.0),
            "L_ankle": _Joint(angle=0.0, neutral=0.0, rom=(-30.0, 30.0), range_deg=20.0),
            "R_ankle": _Joint(angle=0.0, neutral=0.0, rom=(-30.0, 30.0), range_deg=20.0),
        }
        self.trunk_tilt = 0.0
        self.trunk_vel = 0.0
        self._emg = {}
        self._prev_angles = {k: j.angle for k, j in self.joints.items()}
        if self.use_muscles:
            self._muscles = {
                f"{side}_{g}": HillMuscle()
                for side in ("L", "R")
                for pair in _JOINT_MUSCLES.values()
                for g in pair
            }

    def _muscle_net(self, side: str, joint: str, ga: str, gb: str,
                    a: dict[str, float], dt: float) -> float:
        """Net normalized force (agonist − antagonist) via Hill muscles, with
        activation dynamics and force-length/velocity from the joint state."""
        j = self.joints[f"{side}_{joint}"]
        rel = (j.angle - j.neutral) / j.range_deg
        vel = j.vel / j.range_deg  # normalized angular velocity (1/s)
        ma, mb = self._muscles[f"{side}_{ga}"], self._muscles[f"{side}_{gb}"]
        ma.update_activation(self._act(a, f"{side}_{ga}"), dt)
        mb.update_activation(self._act(a, f"{side}_{gb}"), dt)
        len_a = min(1.5, max(0.5, 1.0 - 0.35 * rel))
        len_b = min(1.5, max(0.5, 1.0 + 0.35 * rel))
        fa = ma.force(len_a, 0.35 * vel)
        fb = mb.force(len_b, -0.35 * vel)
        return fa - fb

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _act(activations: dict[str, float], key: str) -> float:
        return max(0.0, min(1.0, activations.get(key, 0.0)))

    def _foot_height(self, side: str) -> float:
        """Foot clearance above ground (m). Smaller = closer to ground.

        У спрощеній пінхоп-моделі (нерухомий таз) обертання стегна штучно
        піднімало б стопу, бо тіло не переноситься вперед над опорою. Тому
        кліренс рахуємо за РЕАЛЬНИМ механізмом підйому стопи у swing — згином
        коліна (і трохи гомілковостопу), а стегно лише виносить стопу
        вперед/назад, не змінюючи висоти. Це навмисне спрощення (канон §2).
        """
        knee = math.radians(self.joints[f"{side}_knee"].angle)
        ankle = math.radians(self.joints[f"{side}_ankle"].angle)
        drop = THIGH_LEN + SHANK_LEN * math.cos(knee)
        clearance = HIP_HEIGHT - drop  # rises as the knee flexes
        clearance += 0.03 * max(0.0, math.sin(ankle))  # slight dorsiflexion lift
        return clearance

    # -------------------------------------------------------------------- step
    def step(self, activations: dict[str, float], t: float, dt: float) -> SensorFrame:
        a = activations
        # Drive each joint from its antagonist pair — either instantaneous net
        # activation, or (opt-in) net force from Hill-type muscles.
        for side in ("L", "R"):
            if self.use_muscles:
                net_hip = self._muscle_net(side, "hip", "hip_flex", "hip_ext", a, dt)
                net_knee = self._muscle_net(side, "knee", "knee_flex", "knee_ext", a, dt)
                net_ankle = self._muscle_net(side, "ankle", "ankle_dorsi", "ankle_plantar", a, dt)
            else:
                net_hip = self._act(a, f"{side}_hip_flex") - self._act(a, f"{side}_hip_ext")
                net_knee = self._act(a, f"{side}_knee_flex") - self._act(a, f"{side}_knee_ext")
                net_ankle = (self._act(a, f"{side}_ankle_dorsi")
                             - self._act(a, f"{side}_ankle_plantar"))
            self.joints[f"{side}_hip"].integrate(net_hip, dt)
            self.joints[f"{side}_knee"].integrate(net_knee, dt)
            self.joints[f"{side}_ankle"].integrate(net_ankle, dt)

        # Trunk: stabilizers resist lean; asymmetric hip drive perturbs it.
        stab = 0.5 * (self._act(a, "L_trunk_stab") + self._act(a, "R_trunk_stab"))
        hip_asym = (self.joints["L_hip"].angle - self.joints["R_hip"].angle)
        disturb = 0.02 * hip_asym
        trunk_target = disturb * (1.0 - 0.8 * stab)
        ta = 120.0 * (trunk_target - self.trunk_tilt) - 12.0 * self.trunk_vel
        self.trunk_vel += ta * dt
        self.trunk_tilt += self.trunk_vel * dt

        # Ground reaction forces from foot heights (soft contact).
        grf = {}
        contact_threshold = 0.06  # m above lowest reachable point counts as loading
        loads = {}
        for side in ("L", "R"):
            fy = self._foot_height(side)
            penetration = max(0.0, contact_threshold - fy)
            loads[side] = penetration
        total = loads["L"] + loads["R"]
        for side in ("L", "R"):
            share = (loads[side] / total) if total > 1e-9 else 0.5
            # When neither foot is "down", body is in flight/unsupported -> low GRF.
            support = min(1.0, total / contact_threshold)
            grf[side] = BODY_WEIGHT_N * share * support

        # Synthetic EMG: low-pass of activation per group.
        emg = {}
        for gid in a:
            prev = self._emg.get(gid, 0.0)
            emg[gid] = prev + 0.3 * (self._act(a, gid) - prev)
        self._emg = emg

        # IMU: gyro ~ joint angular velocities; accel ~ angle accel proxy.
        imu = {}
        joint_angles = {}
        for k, j in self.joints.items():
            joint_angles[k] = j.angle
            imu[f"{k}_gyro"] = j.vel
        imu["trunk_gyro"] = self.trunk_vel
        joint_angles["trunk"] = self.trunk_tilt

        self._prev_angles = {k: j.angle for k, j in self.joints.items()}
        return SensorFrame(t=t, imu=imu, joint_angles=joint_angles, grf=grf, emg=emg)

    def pose(self) -> dict[str, float]:
        p = {k: j.angle for k, j in self.joints.items()}
        p["trunk"] = self.trunk_tilt
        for side in ("L", "R"):
            p[f"{side}_foot_y"] = self._foot_height(side)
        return p
