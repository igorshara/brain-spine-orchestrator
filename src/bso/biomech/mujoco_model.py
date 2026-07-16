"""MuJoCo planar-biped backend (dynamic physics) behind the BioMechModel API.

Динамічний фізичний бекенд: планарний (сагітальний) двоногий у MuJoCo з підвісом
часткового розвантаження ваги (як реабілітаційні поручні/харнес — саме так роблять
ці експерименти, і це тримає фігуру без RL-балансира). Стимуляція переводиться у
референсні кути суглобів, а PD-контролери дають МОМЕНТИ; MuJoCo рахує динаміку й
КОНТАКТНІ сили. Тому GRF, інерція й удар стопи — справжні, а не задані кінематично.

Це навмисний «PD-трекінг референсу» (канон §5 stack: «далі MuJoCo»): диригент
лишається CPG-контролером, фізика лише робить рух тілесним. Усе ILLUSTRATIVE.

Потрібен пакет ``mujoco`` (pip install mujoco).
"""

from __future__ import annotations

import math

import numpy as np

from ..schemas import SensorFrame
from .base import BioMechModel

_XML = """
<mujoco model="bso_planar_biped">
  <option timestep="0.001" gravity="0 0 -9.81" integrator="implicitfast"/>
  <default>
    <joint armature="0.02" damping="1.0"/>
    <geom contype="1" conaffinity="1" friction="1.5 0.1 0.1" solref="0.02 1" solimp="0.9 0.95 0.001"/>
  </default>
  <worldbody>
    <geom name="floor" type="plane" size="20 5 0.1" pos="0 0 0"/>
    <body name="pelvis" pos="0 0 0.90">
      <joint name="pelvis_x" type="slide" axis="1 0 0" damping="3"/>
      <joint name="pelvis_z" type="slide" axis="0 0 1" damping="20" stiffness="3500" springref="0"/>
      <joint name="pelvis_pitch" type="hinge" axis="0 1 0" damping="20" stiffness="220" springref="0"/>
      <geom name="torso" type="capsule" fromto="0 0 0 0 0 0.45" size="0.06" mass="28"/>
      <body name="L_thigh" pos="0 0.09 0">
        <joint name="L_hip" type="hinge" axis="0 1 0" range="-60 90"/>
        <geom type="capsule" fromto="0 0 0 0 0 -0.42" size="0.05" mass="7"/>
        <body name="L_shank" pos="0 0 -0.42">
          <joint name="L_knee" type="hinge" axis="0 1 0" range="0 140"/>
          <geom type="capsule" fromto="0 0 0 0 0 -0.42" size="0.04" mass="3"/>
          <body name="L_foot" pos="0 0 -0.42">
            <joint name="L_ankle" type="hinge" axis="0 1 0" range="-40 40"/>
            <geom name="L_foot_g" type="capsule" fromto="-0.05 0 -0.04 0.16 0 -0.04" size="0.03" mass="1"/>
          </body>
        </body>
      </body>
      <body name="R_thigh" pos="0 -0.09 0">
        <joint name="R_hip" type="hinge" axis="0 1 0" range="-60 90"/>
        <geom type="capsule" fromto="0 0 0 0 0 -0.42" size="0.05" mass="7"/>
        <body name="R_shank" pos="0 0 -0.42">
          <joint name="R_knee" type="hinge" axis="0 1 0" range="0 140"/>
          <geom type="capsule" fromto="0 0 0 0 0 -0.42" size="0.04" mass="3"/>
          <body name="R_foot" pos="0 0 -0.42">
            <joint name="R_ankle" type="hinge" axis="0 1 0" range="-40 40"/>
            <geom name="R_foot_g" type="capsule" fromto="-0.05 0 -0.04 0.16 0 -0.04" size="0.03" mass="1"/>
          </body>
        </body>
      </body>
    </body>
  </worldbody>
  <actuator>
    <motor name="m_L_hip" joint="L_hip" gear="1" ctrlrange="-300 300"/>
    <motor name="m_L_knee" joint="L_knee" gear="1" ctrlrange="-300 300"/>
    <motor name="m_L_ankle" joint="L_ankle" gear="1" ctrlrange="-150 150"/>
    <motor name="m_R_hip" joint="R_hip" gear="1" ctrlrange="-300 300"/>
    <motor name="m_R_knee" joint="R_knee" gear="1" ctrlrange="-300 300"/>
    <motor name="m_R_ankle" joint="R_ankle" gear="1" ctrlrange="-150 150"/>
    <motor name="m_trunk" joint="pelvis_pitch" gear="1" ctrlrange="-400 400"/>
  </actuator>
</mujoco>
"""

# Reference-angle mapping from net activation (mirrors the kinematic model so the
# same CPG drives both). neutral + range_deg * net, with net in [-1, 1].
# Hip range is negative so that hip-FLEXION drives the thigh forward (+x) in this
# model's joint convention — i.e. the biped walks forward, not backward.
_JOINT_MAP = {
    "hip": {"neutral": -3.0, "range": -28.0},
    "knee": {"neutral": 5.0, "range": 50.0},
    "ankle": {"neutral": 0.0, "range": 15.0},
}
_PD_KP = {"hip": 320.0, "knee": 450.0, "ankle": 90.0}
_PD_KD = {"hip": 14.0, "knee": 18.0, "ankle": 4.0}
_ACTUATED = ["L_hip", "L_knee", "L_ankle", "R_hip", "R_knee", "R_ankle"]

# Active trunk balance: the trunk_stab activation GATES an upright-tracking PD on
# the pelvis pitch. When feedback senses a tilt it boosts trunk_stab, which
# raises the corrective torque -> active balance recovery (not just a passive
# harness). ILLUSTRATIVE gains.
_TRUNK_KP = 600.0
_TRUNK_KD = 40.0


class MuJoCoModel(BioMechModel):
    """Dynamic planar biped. Drop-in for KinematicModel via build_system(model=...)."""

    def __init__(self, substeps: int = 5) -> None:
        import mujoco  # local import so core never hard-depends on mujoco

        self._mj = mujoco
        self.model = mujoco.MjModel.from_xml_string(_XML)
        self.data = mujoco.MjData(self.model)
        self.substeps = substeps
        self._qadr = {j: self.model.joint(j).qposadr[0] for j in _ACTUATED}
        self._vadr = {j: self.model.joint(j).dofadr[0] for j in _ACTUATED}
        self._foot_gid = {
            "L": self.model.geom("L_foot_g").id,
            "R": self.model.geom("R_foot_g").id,
        }
        self._pitch_qadr = self.model.joint("pelvis_pitch").qposadr[0]
        self._pitch_vadr = self.model.joint("pelvis_pitch").dofadr[0]
        self._trunk_act = self.model.actuator("m_trunk").id
        self.active_balance = True  # when False, trunk relies on the passive harness only
        self.reset()

    def perturb(self, pitch_velocity_rad_s: float) -> None:
        """Inject an external trunk perturbation (a push): add angular velocity to
        the pelvis pitch DOF. Used by balance-recovery demos/tests."""
        self.data.qvel[self._pitch_vadr] += pitch_velocity_rad_s

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _net(a: dict[str, float], pos: str, neg: str) -> float:
        return max(0.0, min(1.0, a.get(pos, 0.0))) - max(0.0, min(1.0, a.get(neg, 0.0)))

    def _refs(self, a: dict[str, float]) -> dict[str, float]:
        refs = {}
        for side in ("L", "R"):
            hip = self._net(a, f"{side}_hip_flex", f"{side}_hip_ext")
            knee = self._net(a, f"{side}_knee_flex", f"{side}_knee_ext")
            ankle = self._net(a, f"{side}_ankle_dorsi", f"{side}_ankle_plantar")
            refs[f"{side}_hip"] = _JOINT_MAP["hip"]["neutral"] + _JOINT_MAP["hip"]["range"] * hip
            refs[f"{side}_knee"] = _JOINT_MAP["knee"]["neutral"] + _JOINT_MAP["knee"]["range"] * knee
            refs[f"{side}_ankle"] = (
                _JOINT_MAP["ankle"]["neutral"] + _JOINT_MAP["ankle"]["range"] * ankle
            )
        return refs

    def _grf(self) -> dict[str, float]:
        g = {"L": 0.0, "R": 0.0}
        f6 = np.zeros(6)
        for i in range(self.data.ncon):
            c = self.data.contact[i]
            for side, gid in self._foot_gid.items():
                if c.geom1 == gid or c.geom2 == gid:
                    self._mj.mj_contactForce(self.model, self.data, i, f6)
                    g[side] += abs(float(f6[0]))  # normal component (contact frame x)
        return g

    # -------------------------------------------------------------------- step
    def reset(self) -> None:
        self._mj.mj_resetData(self.model, self.data)
        self.data.qpos[self._qadr["L_knee"]] = math.radians(5.0)
        self.data.qpos[self._qadr["R_knee"]] = math.radians(5.0)
        self._mj.mj_forward(self.model, self.data)

    def step(self, activations: dict[str, float], t: float, dt: float) -> SensorFrame:
        refs = self._refs(activations)
        trunk_stab = 0.5 * (
            max(0.0, min(1.0, activations.get("L_trunk_stab", 0.0)))
            + max(0.0, min(1.0, activations.get("R_trunk_stab", 0.0)))
        )
        for _ in range(self.substeps):
            for k, j in enumerate(_ACTUATED):
                joint = j.split("_")[1]
                q = self.data.qpos[self._qadr[j]]
                qd = self.data.qvel[self._vadr[j]]
                r = math.radians(refs[j])
                self.data.ctrl[k] = _PD_KP[joint] * (r - q) - _PD_KD[joint] * qd
            # Active trunk balance: stab-gated PD toward upright (pitch = 0).
            if self.active_balance:
                pitch = self.data.qpos[self._pitch_qadr]
                pitch_vel = self.data.qvel[self._pitch_vadr]
                self.data.ctrl[self._trunk_act] = (
                    _TRUNK_KP * trunk_stab * (0.0 - pitch) - _TRUNK_KD * trunk_stab * pitch_vel
                )
            else:
                self.data.ctrl[self._trunk_act] = 0.0
            self._mj.mj_step(self.model, self.data)

        joint_angles = {j: math.degrees(self.data.qpos[self._qadr[j]]) for j in _ACTUATED}
        joint_angles["trunk"] = math.degrees(self.data.qpos[self.model.joint("pelvis_pitch").qposadr[0]])
        imu = {f"{j}_gyro": float(self.data.qvel[self._vadr[j]]) for j in _ACTUATED}
        imu["trunk_gyro"] = float(self.data.qvel[self.model.joint("pelvis_pitch").dofadr[0]])
        emg = {gid: max(0.0, min(1.0, v)) for gid, v in activations.items()}
        return SensorFrame(t=t, imu=imu, joint_angles=joint_angles, grf=self._grf(), emg=emg)

    def pose(self) -> dict[str, float]:
        p = {j: math.degrees(self.data.qpos[self._qadr[j]]) for j in _ACTUATED}
        p["trunk"] = math.degrees(self.data.qpos[self.model.joint("pelvis_pitch").qposadr[0]])
        for side in ("L", "R"):
            p[f"{side}_foot_y"] = float(self.data.geom(f"{side}_foot_g").xpos[2])
        p["pelvis_x"] = float(self.data.qpos[self.model.joint("pelvis_x").qposadr[0]])
        p["pelvis_z"] = 0.90 + float(self.data.qpos[self.model.joint("pelvis_z").qposadr[0]])
        return p
