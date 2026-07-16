"""OpenSim analysis layer — drive a VALIDATED musculoskeletal model with our gait.

Шар достовірності на реальній валідованій м'язово-скелетній моделі OpenSim
(``gait10dof18musc`` — стандартна модель лінії Delp/Thelen: 18 м'язів Хілла, 10 ст.
свободи, відомі моменти плеч і параметри волокон). Ми НЕ вигадуємо біомеханіку:
беремо патерн суглобових кутів від нашого оркестратора, ПРИПИСУЄМО його реальній
моделі (prescribed kinematics — стабільно, без падінь) і зчитуємо РЕАЛЬНІ довжини
м'язово-сухожилкових одиниць та анатомічні позиції сегментів.

Це чесний і надійний апгрейд достовірності: «наш патерн → валідована модель →
реальні м'язові екскурсії». Повна м'язово-керована динаміка під розімкнутим CPG
впала б — тому ми навмисно робимо кінематичний аналіз, а не нестабільну forward-
динаміку. Потрібен пакет ``opensim`` і файл моделі (models/gait10dof18musc.osim).
"""

from __future__ import annotations

import math
import os

# Our muscle groups -> the model's real muscles (anatomically correct mapping).
MUSCLE_GROUP_MAP = {
    "hip_flex": ["iliopsoas", "rect_fem"],
    "hip_ext": ["glut_max", "hamstrings"],
    "knee_flex": ["hamstrings", "bifemsh"],
    "knee_ext": ["vasti", "rect_fem"],
    "ankle_dorsi": ["tib_ant"],
    "ankle_plantar": ["gastroc", "soleus"],
}
DEFAULT_MODEL = os.path.join(os.path.dirname(__file__), "..", "..", "..", "models",
                             "gait10dof18musc.osim")
_LEG_BODIES = ["femur", "tibia", "calcn", "toes"]


# Which muscle-group activation drives each real muscle (one source per muscle).
_MUSCLE_DRIVE = {
    "iliopsoas": "hip_flex", "glut_max": "hip_ext",
    "hamstrings": "knee_flex", "bifemsh": "knee_flex",
    "rect_fem": "knee_ext", "vasti": "knee_ext",
    "gastroc": "ankle_plantar", "soleus": "ankle_plantar", "tib_ant": "ankle_dorsi",
}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def run_muscle_driven(act_series: list[dict], times: list[float], t_start: float = 1.0,
                      duration: float = 3.0, dt_sample: float = 0.05,
                      model_path: str | None = None, with_transforms: bool = False) -> dict:
    """MUSCLE-DRIVEN forward dynamics on the validated model.

    Our orchestrator's per-group activations become time-varying excitations of the
    model's 18 Hill muscles; with the pelvis externally supported (body-weight
    support — like a rehab frame) the legs MOVE UNDER MUSCLE ACTION (true forward
    dynamics, not prescribed kinematics). Returns joint trajectories + figures."""
    import math as _m

    import opensim as osim
    try:
        osim.Logger.setLevelString("Off")
    except Exception:
        pass
    model = osim.Model(model_path or os.path.abspath(DEFAULT_MODEL))
    for cn in ("pelvis_tx", "pelvis_ty", "pelvis_tilt", "lumbar_extension"):
        model.getCoordinateSet().get(cn).setDefaultLocked(True)

    ctrl = osim.PrescribedController()
    muscles = model.getMuscles()
    for i in range(muscles.getSize()):
        ctrl.addActuator(muscles.get(i))
    sidx = [i for i in range(len(times)) if times[i] >= t_start][::10]
    base_t = times[sidx[0]]
    for i in range(muscles.getSize()):
        nm = muscles.get(i).getName()
        base, side = "_".join(nm.split("_")[:-1]), nm.split("_")[-1].upper()
        grp = f"{side}_{_MUSCLE_DRIVE[base]}"
        fn = osim.PiecewiseLinearFunction()
        for j in sidx:
            fn.addPoint(times[j] - base_t, _clamp(act_series[j].get(grp, 0.0), 0.02, 1.0))
        ctrl.prescribeControlForActuator(nm, fn)
    model.addController(ctrl)

    state = model.initSystem()
    state.setTime(0.0)
    cs = model.getCoordinateSet()
    mgr = osim.Manager(model)
    mgr.initialize(state)

    out = {k: [] for k in ("t", "L_hip", "R_hip", "L_knee", "R_knee", "L_ankle", "R_ankle")}
    figures = []
    figures3d = []
    transforms = []
    n = int(duration / dt_sample)
    for k in range(1, n + 1):
        state = mgr.integrate(k * dt_sample)
        out["t"].append(k * dt_sample)
        for side in ("l", "r"):
            S = side.upper()
            out[f"{S}_hip"].append(_m.degrees(cs.get(f"hip_flexion_{side}").getValue(state)))
            out[f"{S}_knee"].append(-_m.degrees(cs.get(f"knee_angle_{side}").getValue(state)))
            out[f"{S}_ankle"].append(_m.degrees(cs.get(f"ankle_angle_{side}").getValue(state)))
        pts = {"pelvis": _xy(model, state, "pelvis"), "torso": _xy(model, state, "torso")}
        for side in ("l", "r"):
            pts[side] = [_xy(model, state, "pelvis")] + [_xy(model, state, f"{b}_{side}")
                                                         for b in _LEG_BODIES]
        figures.append(pts)
        p3 = {"pelvis": _xyz(model, state, "pelvis"), "torso": _xyz(model, state, "torso")}
        for side in ("l", "r"):
            p3[side] = [_xyz(model, state, "pelvis")] + [_xyz(model, state, f"{b}_{side}")
                                                        for b in _LEG_BODIES]
        figures3d.append(p3)
        if with_transforms:
            transforms.append({b: _body_matrix(model, state, b) for b in _BODY_MESHES})
    out["figures"] = figures
    out["figures3d"] = figures3d
    if with_transforms:
        out["transforms"] = transforms
    return out


# Bone meshes per body (merged) for 3D rendering.
_BODY_MESHES = {
    "pelvis": ["pelvis.vtp", "sacrum.vtp", "l_pelvis.vtp"],
    "femur_r": ["femur_r.vtp"], "femur_l": ["femur_l.vtp"],
    "tibia_r": ["tibia_r.vtp", "fibula.vtp"], "tibia_l": ["tibia_l.vtp", "l_fibula.vtp"],
    "talus_r": ["talus.vtp"], "talus_l": ["l_talus.vtp"],
    "calcn_r": ["foot.vtp"], "calcn_l": ["l_foot.vtp"],
    "toes_r": ["bofoot.vtp"], "toes_l": ["l_bofoot.vtp"],
    "torso": ["hat_spine.vtp", "hat_ribs.vtp", "hat_skull.vtp", "hat_jaw.vtp"],
}
_GEOM_DIR = os.path.join(os.path.dirname(DEFAULT_MODEL), "Geometry")


def parse_vtp(path: str):
    """Parse an ASCII VTK PolyData (.vtp) -> (verts flat [x,y,z,...], faces [i,j,k,...])."""
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    piece = root.find(".//Piece")
    verts, conn, offs = [], [], []
    pts = piece.find("Points").find("DataArray")
    verts = [float(x) for x in pts.text.split()]
    polys = piece.find("Polys")
    for da in polys.findall("DataArray"):
        nums = da.text.split()
        if da.get("Name") == "connectivity":
            conn = [int(x) for x in nums]
        elif da.get("Name") == "offsets":
            offs = [int(x) for x in nums]
    faces, prev = [], 0
    for o in offs:
        idx = conn[prev:o]
        for k in range(1, len(idx) - 1):  # fan-triangulate
            faces += [idx[0], idx[k], idx[k + 1]]
        prev = o
    return verts, faces


def load_body_meshes() -> dict:
    """Merge each body's .vtp meshes into one {verts, faces} (in the body frame)."""
    out = {}
    for body, files in _BODY_MESHES.items():
        verts, faces = [], []
        for f in files:
            p = os.path.join(_GEOM_DIR, f)
            if not os.path.exists(p):
                continue
            v, fc = parse_vtp(p)
            base = len(verts) // 3
            verts += v
            faces += [i + base for i in fc]
        if verts:
            out[body] = {"verts": verts, "faces": faces}
    return out


def _body_matrix(model, state, name) -> list:
    """4x4 column-major transform of a body in ground (for three.js Matrix4)."""
    t = model.getBodySet().get(name).getTransformInGround(state)
    R, p = t.R(), t.p()
    return [R.get(0, 0), R.get(1, 0), R.get(2, 0), 0.0,
            R.get(0, 1), R.get(1, 1), R.get(2, 1), 0.0,
            R.get(0, 2), R.get(1, 2), R.get(2, 2), 0.0,
            p.get(0), p.get(1), p.get(2), 1.0]


def _xy(model, state, name):
    p = model.getBodySet().get(name).getPositionInGround(state)
    return float(p.get(0)), float(p.get(1))


def _xyz(model, state, name):
    p = model.getBodySet().get(name).getPositionInGround(state)
    return [float(p.get(0)), float(p.get(1)), float(p.get(2))]


class OpenSimGaitAnalyzer:
    """Prescribes our gait kinematics onto the validated model and reports real
    muscle-tendon lengths and segment positions. Pure analysis — never falls."""

    def __init__(self, model_path: str | None = None) -> None:
        import opensim as osim  # local import; OpenSim is optional

        self._osim = osim
        try:
            osim.Logger.setLevelString("Off")  # silence missing-geometry warnings
        except Exception:
            pass
        self.model = osim.Model(model_path or os.path.abspath(DEFAULT_MODEL))
        self.state = self.model.initSystem()
        self.coords = self.model.getCoordinateSet()
        self.muscle_names = [m.getName() for m in self.model.getMuscles()]

    def _set_pose(self, hip_l, knee_l, ankle_l, hip_r, knee_r, ankle_r):
        # Our convention -> model convention. Knee flexion is NEGATIVE in the model.
        def setc(name, deg, lo, hi):
            self.coords.get(name).setValue(self.state, math.radians(_clamp(deg, lo, hi)), False)
        setc("hip_flexion_l", hip_l, -120, 120)
        setc("hip_flexion_r", hip_r, -120, 120)
        setc("knee_angle_l", -knee_l, -120, 10)
        setc("knee_angle_r", -knee_r, -120, 10)
        setc("ankle_angle_l", ankle_l, -90, 90)
        setc("ankle_angle_r", ankle_r, -90, 90)
        self.model.assemble(self.state)
        self.model.realizePosition(self.state)

    def analyze(self, frames: list[dict]) -> dict:
        """frames: list of {L_hip,L_knee,L_ankle,R_hip,R_knee,R_ankle} in degrees
        (our convention). Returns real muscle lengths per frame and sagittal
        segment points for an anatomically-proportioned figure."""
        lengths = {n: [] for n in self.muscle_names}
        figures = []
        for f in frames:
            self._set_pose(f["L_hip"], f["L_knee"], f["L_ankle"],
                           f["R_hip"], f["R_knee"], f["R_ankle"])
            for n in self.muscle_names:
                lengths[n].append(float(self.model.getMuscles().get(n).getLength(self.state)))
            figures.append(self._sagittal_points())
        return {"muscle_lengths": lengths, "figures": figures, "muscles": self.muscle_names}

    def _body_xy(self, name: str) -> tuple[float, float]:
        p = self.model.getBodySet().get(name).getPositionInGround(self.state)
        return float(p.get(0)), float(p.get(1))  # (anterior, vertical) sagittal plane

    def _sagittal_points(self) -> dict:
        pts = {"pelvis": self._body_xy("pelvis"), "torso": self._body_xy("torso")}
        for side in ("l", "r"):
            pts[side] = [self._body_xy("pelvis")] + [self._body_xy(f"{b}_{side}")
                                                     for b in _LEG_BODIES]
        return pts

    def group_to_muscles(self) -> dict[str, list[str]]:
        out = {}
        for side in ("L", "R"):
            sfx = side.lower()
            for action, muscles in MUSCLE_GROUP_MAP.items():
                out[f"{side}_{action}"] = [f"{mm}_{sfx}" for mm in muscles
                                           if f"{mm}_{sfx}" in self.muscle_names]
        return out
