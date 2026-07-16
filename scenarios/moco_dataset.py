"""Many-solve distillation: a robust real-time policy from Moco across speeds.

Проганяємо MocoInverse на КІЛЬКОХ швидкостях ходи, збираємо різноманітні пари
«стан суглобів (+ швидкість) -> оптимальні м'язові збудження» і навчаємо ОДНУ
політику, що узагальнює на швидкості. Перевіряємо на ВІДКЛАДЕНІЙ швидкості —
це показує робастність, а не запамʼятовування. Самоставить DYLD для IPOPT.

Запуск:  python3 scenarios/moco_dataset.py
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
from bso.distill import MLPRegressor, r2  # noqa: E402
from bso.runtime import build_system  # noqa: E402
from bso.schemas import Mode  # noqa: E402

SPEEDS = [0.30, 0.40, 0.45, 0.55, 0.60, 0.70]
HELDOUT = 0.5  # interpolation test: neighbours at 0.45 and 0.55


def _features(rec, t, speed):
    i = min(len(rec.t) - 2, max(1, int(t / 0.005)))
    p, pm = rec.pose[i], rec.pose[i - 1]
    keys = ("L_hip", "R_hip", "L_knee", "R_knee", "L_ankle", "R_ankle")
    ang = [p[k] / 100.0 for k in keys]
    vel = [(p[k] - pm[k]) / 0.005 / 300.0 for k in keys]
    ph = (rec.gait_phase[i] or {}).get("cycle_phase", 0.0)
    return ang + vel + [math.sin(2 * math.pi * ph), math.cos(2 * math.pi * ph), speed]


def _solve_speed(speed):
    from moco_inverse import build_problem
    inv = build_problem(window=0.7, speed=speed)
    sol = inv.solve()
    ms = sol.getMocoSolution()
    if not ms.success():
        ms.unseal()
        return None
    ms.write("/tmp/ds_sol.sto")
    lines = open("/tmp/ds_sol.sto").read().splitlines()
    hi = [i for i, ln in enumerate(lines) if ln.strip() == "endheader"][0]
    cols = lines[hi + 1].split("\t")
    rows = [[float(x) for x in ln.split("\t")] for ln in lines[hi + 2:] if ln.strip()]
    t = [r[0] for r in rows]
    mcols = [(j, c.split("/")[-1]) for j, c in enumerate(cols)
             if "/forceset/" in c and "reserve" not in c.lower()]
    names = [n for _, n in mcols]
    Y = np.array([[r[j] for j, _ in mcols] for r in rows])
    rec = build_system([IntentEvent(0.0, Mode.STAND),
                        IntentEvent(1.0, Mode.WALK, speed=speed)]).run(4.0)
    X = np.array([_features(rec, tt, speed) for tt in t])
    return X, Y, names


def main() -> None:
    print("=== Many-solve distillation: robust real-time policy across speeds ===")
    data = {}
    names = None
    for sp in sorted(set(SPEEDS + [HELDOUT])):
        out = _solve_speed(sp)
        if out is None:
            print(f"  speed {sp}: did not converge (skipped)")
            continue
        X, Y, names = out
        data[sp] = (X, Y)
        print(f"  speed {sp}: solved, {len(X)} state->excitation pairs")
    if len([s for s in data if s != HELDOUT]) < 2:
        print("  too few converged solves to train robustly.")
        return

    def stack(speeds):
        Xs = np.vstack([data[s][0] for s in speeds])
        Ys = np.vstack([data[s][1] for s in speeds])
        return Xs, Ys

    train_speeds = [s for s in data if s != HELDOUT]
    Xtr, Ytr = stack(train_speeds)
    pol = MLPRegressor(n_in=Xtr.shape[1], n_out=Ytr.shape[1], n_hidden=20, l2=3e-3)
    pol.fit(Xtr, Ytr, epochs=4000, lr=5e-3)
    print(f"\n  trained on speeds {train_speeds}: {len(Xtr)} pairs, "
          f"train R2={r2(Ytr, pol.forward(Xtr)):.3f}")
    if HELDOUT in data:
        Xh, Yh = data[HELDOUT]
        rh = r2(Yh, pol.forward(Xh))
        verdict = ("generalizes to the unseen speed" if rh > 0.5 else
                   "does NOT yet generalize (honest negative — needs more solves / structure)")
        print(f"  HELD-OUT speed {HELDOUT} (never trained): R2={rh:.3f} -> {verdict}")
    out = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "distilled_policy_multi.json")
    pol.save(out)
    print("  saved robust policy ->", out)
    print("  -> one real-time policy covers a range of walking speeds (speed-conditioned).")


if __name__ == "__main__":
    main()
