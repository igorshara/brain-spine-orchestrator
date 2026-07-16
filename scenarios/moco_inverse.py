"""MocoInverse: muscle excitations for weight-bearing gait (optimal control).

Налаштування задачі оптимального керування OpenSim Moco (MocoInverse): за заданою
кінематикою ходи від нашого CPG розвʼязати М'ЯЗОВІ ЗБУДЖЕННЯ (DeGrooteFregly2016,
жорсткий сухожилок) + резервні моменти. Це коректний шлях до вагоносного м'язового
розвʼязку (баланс — наступним кроком через предиктивний Moco/RL).

СТАН СЕРЕДОВИЩА: pip-білд OpenSim постачає CasADi БЕЗ розвʼязувача IPOPT, тож solve()
кидає «Plugin 'ipopt' is not found». Сетап коректний — щоб розвʼязати, потрібен OpenSim
із conda (несе IPOPT) або зібраний IPOPT. Скрипт обробляє це чесно й не падає.

Запуск:  python3 scenarios/moco_inverse.py
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys

# Make IPOPT findable: the pip OpenSim bundles libgfortran but CasADi's IPOPT
# plugin looks elsewhere. Point dyld at the opensim package dir, then re-exec
# once so `python3 scenarios/moco_inverse.py` just works.
if os.environ.get("_BSO_MOCO_DYLD") != "1":
    spec = importlib.util.find_spec("opensim")
    if spec and spec.origin:
        d = os.path.dirname(spec.origin)
        os.environ["DYLD_LIBRARY_PATH"] = d + ":" + os.environ.get("DYLD_LIBRARY_PATH", "")
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = d
    os.environ["_BSO_MOCO_DYLD"] = "1"
    os.execv(sys.executable, [sys.executable, *sys.argv])

import _bootstrap  # noqa: F401, E402
import numpy as np

from bso.decoder_stub import IntentEvent
from bso.runtime import build_system
from bso.schemas import Mode


def build_problem(window=0.7, dt=0.02, speed=0.5):
    import opensim as osim
    osim.Logger.setLevelString("Error")
    rec = build_system([IntentEvent(0.0, Mode.STAND),
                        IntentEvent(1.0, Mode.WALK, speed=speed)]).run(4.0)
    model = osim.Model("models/gait10dof18musc.osim")
    # foot-ground contact so the inverse solution must SUPPORT BODY WEIGHT
    model.addContactGeometry(osim.ContactHalfSpace(osim.Vec3(0, 0, 0),
                             osim.Vec3(0, 0, -math.pi / 2), model.getGround(), "floor"))
    cnames = []
    spheres = [("h_l", "calcn_l", -0.005), ("t_l", "toes_l", 0.025),
               ("h_r", "calcn_r", -0.005), ("t_r", "toes_r", 0.025)]
    for nm, body, xoff in spheres:
        r = 0.025 if nm.startswith("h") else 0.02
        loc = osim.Vec3(xoff, -0.005, 0)
        model.addContactGeometry(osim.ContactSphere(r, loc, model.getBodySet().get(body), nm))
        cnames.append(nm)
    fl = osim.ContactHalfSpace.safeDownCast(model.getContactGeometrySet().get("floor"))
    for nm in cnames:
        sph = osim.ContactSphere.safeDownCast(model.getContactGeometrySet().get(nm))
        f = osim.SmoothSphereHalfSpaceForce("c_" + nm, sph, fl)
        f.set_stiffness(8e4)
        f.set_dissipation(2.0)
        f.set_static_friction(0.9)
        f.set_dynamic_friction(0.8)
        f.set_viscous_friction(0.5)
        model.addForce(f)
    model.initSystem()
    coords = [model.getCoordinateSet().get(i) for i in range(model.getCoordinateSet().getSize())]
    paths = [c.getAbsolutePathString() + "/value" for c in coords]
    times = np.arange(2.0, 2.0 + window, dt)
    tab = osim.TimeSeriesTable()
    tab.setColumnLabels(osim.StdVectorString(paths))

    def val(tt, c):
        i = min(len(rec.t) - 1, int(tt / 0.005))
        nm, p = c.getName(), rec.pose[i]
        if nm.startswith("hip_flexion"):
            return math.radians(p["R_hip" if nm.endswith("_r") else "L_hip"])
        if nm.startswith("knee_angle"):
            return math.radians(-p["R_knee" if nm.endswith("_r") else "L_knee"])
        if nm.startswith("ankle_angle"):
            return math.radians(p["R_ankle" if nm.endswith("_r") else "L_ankle"])
        return 0.0

    for tt in times:
        tab.appendRow(float(tt), osim.RowVector([val(tt, c) for c in coords]))
    tab.addTableMetaDataString("inDegrees", "no")
    osim.STOFileAdapter.write(tab, "/tmp/cpg_kin.sto")

    inv = osim.MocoInverse()
    mp = osim.ModelProcessor(model)
    mp.append(osim.ModOpReplaceMusclesWithDeGrooteFregly2016())
    mp.append(osim.ModOpIgnoreTendonCompliance())
    mp.append(osim.ModOpIgnoreActivationDynamics())
    mp.append(osim.ModOpAddReserves(1000.0))  # strong reserves -> inverse stays feasible
    inv.setModel(mp)
    tp = osim.TableProcessor("/tmp/cpg_kin.sto")
    tp.append(osim.TabOpLowPassFilter(8))
    inv.setKinematics(tp)
    inv.set_initial_time(float(times[0]))
    inv.set_final_time(float(times[-1]))
    inv.set_mesh_interval(0.05)
    inv.set_kinematics_allow_extra_columns(True)
    return inv


def _export_json(sto_path: str) -> None:
    """Extract muscle excitation time series from the Moco solution -> JSON for the
    dashboard (so it can show soleus/gastroc activation without running Moco)."""
    import json
    lines = open(sto_path).read().splitlines()
    hi = [i for i, ln in enumerate(lines) if ln.strip() == "endheader"][0]
    cols = lines[hi + 1].split("\t")
    rows = [[float(x) for x in ln.split("\t")] for ln in lines[hi + 2:] if ln.strip()]
    t = [r[0] for r in rows]
    muscles = {}
    for j, c in enumerate(cols):
        if j == 0 or "/forceset/" not in c or "reserve" in c.lower():
            continue
        muscles[c.split("/")[-1]] = [round(r[j], 4) for r in rows]
    out = os.path.join(os.path.dirname(__file__), "..", "outputs", "moco_muscles.json")
    with open(out, "w") as f:
        json.dump({"t": [round(x, 3) for x in t], "muscles": muscles}, f)
    print("muscle excitations exported ->", os.path.abspath(out))


def main(window: float = 0.7) -> None:
    print(f"=== MocoInverse — weight-bearing muscle solution (window={window}s) ===")
    try:
        inv = build_problem(window=window)
    except Exception as e:
        print("OpenSim/Moco not available:", e)
        return
    print("problem set up correctly (DeGroote muscles, rigid tendon, reserves).")
    try:
        sol = inv.solve()
        ms = sol.getMocoSolution()
        success = ms.success()
        if not success:
            ms.unseal()
        print(f"MOCO RAN. converged={success}, objective={ms.getObjective():.3f}")
        ms.write("/tmp/moco_inverse_solution.sto")
        print("solution written -> /tmp/moco_inverse_solution.sto")
        _export_json("/tmp/moco_inverse_solution.sto")
        if success:
            print("-> WEIGHT-BEARING muscle excitations solved via optimal control (MocoInverse,")
            print("   foot-ground contact). Honest scope: kinematics are prescribed and solved")
            print("   for muscle activations; full predictive balance is the next step.")
        else:
            print("-> solver ran but did not fully converge; needs mesh/tolerance tuning "
                  "(normal Moco workflow). IPOPT now works (env fix applied).")
    except RuntimeError as e:
        msg = str(e)
        if "ipopt" in msg.lower():
            print("BLOCKED: this OpenSim build's CasADi lacks the IPOPT solver plugin.")
            print("Setup is correct; to solve, install OpenSim via conda (ships IPOPT) "
                  "or build IPOPT. This is an environment step, not a modelling issue.")
        else:
            print("solve error:", msg)


if __name__ == "__main__":
    main(window=float(sys.argv[1]) if len(sys.argv) > 1 else 0.7)
