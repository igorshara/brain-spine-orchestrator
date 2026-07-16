"""Distill the Moco optimum into a real-time policy (behavioral cloning).

Беремо пари «стан суглобів -> оптимальні м'язові збудження» з Moco-розвʼязку
(outputs/moco_muscles.json, згенерований moco_inverse.py) і навчаємо малу нейромережу
відтворювати їх. Результат — швидка політика (мікросекунди/виклик), що видає м'язові
збудження без солвера — придатна для real-time контуру. Усе ILLUSTRATIVE.

Спершу: python3 scenarios/moco_inverse.py 0.7   (створює moco_muscles.json)
Потім:  python3 scenarios/distill_policy.py
"""

from __future__ import annotations

import json
import math
import os
import time

import _bootstrap  # noqa: F401
import numpy as np

from bso.decoder_stub import IntentEvent
from bso.distill import MLPRegressor, r2
from bso.runtime import build_system
from bso.schemas import Mode

MOCO = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "moco_muscles.json")


def _cpg_features(rec, t):
    i = min(len(rec.t) - 2, max(1, int(t / 0.005)))
    p, pm = rec.pose[i], rec.pose[i - 1]
    ang = [p["L_hip"], p["R_hip"], p["L_knee"], p["R_knee"], p["L_ankle"], p["R_ankle"]]
    vel = [(p[k] - pm[k]) / 0.005 for k in ("L_hip", "R_hip", "L_knee", "R_knee",
                                            "L_ankle", "R_ankle")]
    ph = (rec.gait_phase[i] or {}).get("cycle_phase", 0.0)
    return ([a / 100.0 for a in ang] + [v / 300.0 for v in vel]
            + [math.sin(2 * math.pi * ph), math.cos(2 * math.pi * ph)])


def main() -> None:
    if not os.path.exists(MOCO):
        print("run `python3 scenarios/moco_inverse.py 0.7` first to create moco_muscles.json")
        return
    d = json.load(open(MOCO))
    times = np.array(d["t"])
    names = list(d["muscles"])
    Y = np.array([d["muscles"][n] for n in names]).T  # (T, 18) optimal excitations
    rec = build_system([IntentEvent(0.0, Mode.STAND),
                        IntentEvent(1.0, Mode.WALK, speed=0.5)]).run(4.0)
    X = np.array([_cpg_features(rec, t) for t in times])  # (T, 14) joint state

    # densify (the optimal solution is smooth) for stable training
    dense_t = np.linspace(times[0], times[-1], 160)
    Xi = np.column_stack([np.interp(dense_t, times, X[:, j]) for j in range(X.shape[1])])
    Yi = np.column_stack([np.interp(dense_t, times, Y[:, j]) for j in range(Y.shape[1])])
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(Xi))
    ntr = int(0.8 * len(idx))
    tr, va = idx[:ntr], idx[ntr:]

    print("=== Distilling Moco optimum -> real-time policy (behavioral cloning) ===")
    print(f"  data: {len(times)} Moco mesh points -> {len(Xi)} densified pairs "
          f"(14 state features -> {len(names)} muscle excitations)")
    pol = MLPRegressor(n_in=Xi.shape[1], n_out=Yi.shape[1], n_hidden=24)
    pol.fit(Xi[tr], Yi[tr], epochs=4000, lr=5e-3)
    r2_tr = r2(Yi[tr], pol.forward(Xi[tr]))
    r2_va = r2(Yi[va], pol.forward(Xi[va]))
    print(f"  distillation fit: R2 train={r2_tr:.3f}, held-out R2={r2_va:.3f}")

    # real-time speed
    x1 = Xi[:1]
    t0 = time.perf_counter()
    for _ in range(2000):
        pol.forward(x1)
    us = (time.perf_counter() - t0) / 2000 * 1e6
    print(f"  inference: {us:.1f} microseconds/call -> real-time capable "
          f"(~{1e6 / us / 1000:.0f}k calls/s, vs Moco solver = seconds)")

    out = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "distilled_policy.json")
    pol.save(out)
    print("  saved policy ->", out)
    print("  -> the slow offline optimum is now a fast state->excitation policy for a "
          "real-time loop. Honest: trained on one short solve; more solves broaden it.")


if __name__ == "__main__":
    main()
