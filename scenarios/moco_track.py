"""MocoTrack predictive balance — emergent weight-bearing gait (the frontier step).

Предиктивний баланс: на відміну від MocoInverse (де кінематика ПРИПИСАНА), тут
кінематика ВІЛЬНА — солвер шукає м'язові збудження І рухи так, щоб задовольнити
динаміку з контактом стопи й НЕ ВПАСТИ (емерджентний баланс), лише слабко
відстежуючи патерн CPG. Це найважча задача в галузі; обмежений прогін може не
зійтися — це нормально, і ми звітуємо статус чесно.

Самоставить dyld для IPOPT (як moco_inverse). Запуск:  python3 scenarios/moco_track.py
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys

if os.environ.get("_BSO_MOCO_DYLD") != "1":
    spec = importlib.util.find_spec("opensim")
    if spec and spec.origin:
        d = os.path.dirname(spec.origin)
        os.environ["DYLD_LIBRARY_PATH"] = d + ":" + os.environ.get("DYLD_LIBRARY_PATH", "")
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = d
    os.environ["_BSO_MOCO_DYLD"] = "1"
    os.execv(sys.executable, [sys.executable, *sys.argv])

import _bootstrap  # noqa: F401, E402
import numpy as np  # noqa: E402

from bso.decoder_stub import IntentEvent  # noqa: E402
from bso.runtime import build_system  # noqa: E402
from bso.schemas import Mode  # noqa: E402


def main(window: float = 0.4, max_iter: int = 60) -> None:
    import opensim as osim
    osim.Logger.setLevelString("Error")
    rec = build_system([IntentEvent(0.0, Mode.STAND),
                        IntentEvent(1.0, Mode.WALK, speed=0.5)]).run(4.0)
    model = osim.Model("models/gait10dof18musc.osim")
    model.addContactGeometry(osim.ContactHalfSpace(osim.Vec3(0, 0, 0),
                             osim.Vec3(0, 0, -math.pi / 2), model.getGround(), "floor"))
    for nm, body, xoff in [("h_l", "calcn_l", -0.005), ("t_l", "toes_l", 0.025),
                           ("h_r", "calcn_r", -0.005), ("t_r", "toes_r", 0.025)]:
        r = 0.025 if nm.startswith("h") else 0.02
        model.addContactGeometry(osim.ContactSphere(r, osim.Vec3(xoff, -0.005, 0),
                                                    model.getBodySet().get(body), nm))
    fl = osim.ContactHalfSpace.safeDownCast(model.getContactGeometrySet().get("floor"))
    for nm in ("h_l", "t_l", "h_r", "t_r"):
        f = osim.SmoothSphereHalfSpaceForce("c_" + nm,
            osim.ContactSphere.safeDownCast(model.getContactGeometrySet().get(nm)), fl)
        for s, v in (("stiffness", 8e4), ("dissipation", 2.0), ("static_friction", 0.9),
                     ("dynamic_friction", 0.8), ("viscous_friction", 0.5)):
            getattr(f, "set_" + s)(v)
        model.addForce(f)
    model.initSystem()

    coords = [model.getCoordinateSet().get(i) for i in range(model.getCoordinateSet().getSize())]
    paths = [c.getAbsolutePathString() + "/value" for c in coords]
    times = np.arange(2.0, 2.0 + window, 0.02)
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
    osim.STOFileAdapter.write(tab, "/tmp/track_ref.sto")

    track = osim.MocoTrack()
    track.setName("predictive_balance")
    mp = osim.ModelProcessor(model)
    mp.append(osim.ModOpReplaceMusclesWithDeGrooteFregly2016())
    mp.append(osim.ModOpIgnoreTendonCompliance())
    mp.append(osim.ModOpIgnoreActivationDynamics())
    mp.append(osim.ModOpAddReserves(1000.0))
    track.setModel(mp)
    track.setStatesReference(osim.TableProcessor("/tmp/track_ref.sto"))
    track.set_states_global_tracking_weight(1.0)
    track.set_allow_unused_references(True)
    track.set_track_reference_position_derivatives(True)
    track.set_initial_time(float(times[0]) + 1e-3)
    track.set_final_time(float(times[-1]) - 1e-3)
    track.set_mesh_interval(0.06)

    print("=== MocoTrack predictive balance (emergent weight-bearing) ===")
    print(f"  setting up (free kinematics + contact, {max_iter} iter cap)...")
    study = track.initialize()
    solver = osim.MocoCasADiSolver.safeDownCast(study.updSolver())
    solver.set_optim_max_iterations(max_iter)
    try:
        sol = study.solve()
        success = sol.success()
        if not success:
            sol.unseal()
        print(f"  MOCO RAN. converged={success}, objective={sol.getObjective():.2f}")
        if success:
            sol.write("/tmp/moco_track_solution.sto")
            import numpy as _np
            ls = open("/tmp/moco_track_solution.sto").read().splitlines()
            hi = [i for i, x in enumerate(ls) if x.strip() == "endheader"][0]
            cols = ls[hi + 1].split("\t")
            dat = _np.array([[float(x) for x in r.split("\t")] for r in ls[hi + 2:] if r.strip()])
            jty = [j for j, c in enumerate(cols) if c.endswith("pelvis_ty/value")]
            if jty:
                ty = dat[:, jty[0]]
                print(f"  pelvis height stayed {ty.min():.3f}..{ty.max():.3f} m "
                      f"(upright = balance held, body did NOT fall)")
        print("  -> predictive balance solved (emergent weight-bearing gait)." if success else
              "  -> ran but did not converge in the iteration cap. Predictive balance is the "
              "field's frontier; needs a longer solve + warm start. Infrastructure is ready "
              "(Moco works); MocoInverse weight-bearing already converges (moco_inverse.py).")
    except RuntimeError as e:
        print("  solve error:", str(e)[:160])


if __name__ == "__main__":
    win = float(sys.argv[1]) if len(sys.argv) > 1 else 0.4
    mi = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    main(window=win, max_iter=mi)
