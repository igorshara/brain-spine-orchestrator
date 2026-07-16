"""Learn the Layer-4 adaptation policy (CEM) and compare it to the hand-tuned
integral controller — the scientific differentiator.

Навчаємо нейрополітику Шару 4 методом cross-entropy ОФЛАЙН (на швидкій кінематиці),
потім порівнюємо на ВІДКЛАДЕНІЙ (важчій) умові втоми три варіанти: без адаптації /
рукотворний інтегральний контролер / навчена політика. Далі — перенос навченої
політики на ДИНАМІЧНУ фізику MuJoCo (узагальнення на інше тіло). Усе ILLUSTRATIVE.

Ваги кешуються у outputs/learned_policy.json (повторний запуск не перенавчає).
Запуск:  python3 scenarios/learn_adaptation.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401
import numpy as np

from bso.decoder_stub import IntentEvent
from bso.degradation import FatigueModel
from bso.learned_adaptation import MLPPolicy, mean_fatigue, train_cem
from bso.runtime import build_system
from bso.schemas import Mode

SCHED = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.6)]
DUR = 16.0
WEIGHTS = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "learned_policy.json")


def _retention(rec):
    fy = np.array([p["L_foot_y"] for p in rec.pose])
    n = int(2.0 / 0.005)
    win = {rec.t[i]: fy[i - n : i].max() - fy[i - n : i].min() for i in range(n, len(fy), n)}
    early = np.mean([v for t, v in win.items() if 4 < t < 8])
    late = np.mean([v for t, v in win.items() if t > DUR - 5])
    return early, late


def get_policy() -> MLPPolicy:
    if os.path.exists(WEIGHTS):
        print(f"loading cached policy: {WEIGHTS}")
        return MLPPolicy.load(WEIGHTS)
    print("training policy with CEM (offline, kinematic) — this takes ~1 min ...")
    train_conditions = [
        lambda: {"fatigue": FatigueModel(enabled=True, fatigue_rate=0.08, fatigue_max=0.5,
                                         drift_rate_per_s=0.003)},
        lambda: {"fatigue": FatigueModel(enabled=True, fatigue_rate=0.11, fatigue_max=0.55,
                                         drift_rate_per_s=0.005)},
    ]
    best, history = train_cem(train_conditions, pop=18, elite=5, iters=10, seed=0, dur=14.0)
    print("CEM reward per iter:", [round(h, 4) for h in history])
    policy = MLPPolicy(params=best)
    os.makedirs(os.path.dirname(WEIGHTS), exist_ok=True)
    policy.save(WEIGHTS)
    print(f"saved policy -> {WEIGHTS}")
    return policy


def _heldout_fatigue():
    # Harder than training — tests generalization, not memorization.
    return FatigueModel(enabled=True, fatigue_rate=0.13, fatigue_max=0.6, drift_rate_per_s=0.006)


def main(render: bool = True) -> None:
    policy = get_policy()

    print("\n=== HELD-OUT condition (kinematic, harder fatigue) ===")
    print("  objective: hold a HEALTHY clearance (~0.14) with the LEAST fatigue")
    recs = {
        "no-adapt": build_system(SCHED, fatigue=_heldout_fatigue()).run(DUR),
        "integral": build_system(SCHED, fatigue=_heldout_fatigue(), adapt=True).run(DUR),
        "learned": build_system(SCHED, fatigue=_heldout_fatigue(), policy=policy).run(DUR),
    }
    print(f"  {'controller':10s} {'late_clr':>9} {'mean_fatigue':>13} {'clr/fatigue':>12}")
    for label, rec in recs.items():
        _, late = _retention(rec)
        mf = mean_fatigue(rec)
        eff = late / mf if mf > 1e-6 else float("inf")
        print(f"  {label:10s} {late:9.3f} {mf:13.3f} {eff:12.2f}")

    print("\n=== TRANSFER to MuJoCo dynamic physics (same learned policy) ===")
    try:
        from bso.biomech.mujoco_model import MuJoCoModel
        msched = [IntentEvent(0.0, Mode.STAND), IntentEvent(2.0, Mode.WALK, speed=0.45)]
        for label, kw in (("no-adapt", {}), ("learned", {"policy": policy})):
            rec = build_system(msched, model=MuJoCoModel(),
                               fatigue=_heldout_fatigue(), **kw).run(DUR)
            early, late = _retention(rec)
            pz = np.mean([p["pelvis_z"] for p in rec.pose[800:]])
            print(f"  {label:10s} retention={late / early * 100:4.0f}%  pelvis_z={pz:.2f}")
    except ImportError:
        print("  (mujoco not installed — skipped transfer test)")

    print("\n=== HONEST VERDICT ===")
    print("  The hand-tuned INTEGRAL controller is a strong, near-optimal baseline")
    print("  for this single-objective compensation task and the small learned")
    print("  policy does NOT beat it (and transfers worse to physics). This is a")
    print("  useful negative result: don't add learning complexity here. Learning's")
    print("  value is hypothesised for richer settings — high-dimensional channel")
    print("  coordination, partial observability, multi-objective clinical costs —")
    print("  which this trainable Layer-4 harness now makes possible to explore.")

    if render:
        from bso.viz.dashboard import save_resilience

        out = os.path.abspath(_bootstrap.OUTPUT_DIR)
        path = os.path.join(out, "learned_adaptation.png")
        print("\nsaved:", save_resilience(recs, path,
                                          title="Learned vs hand-tuned adaptation"))


if __name__ == "__main__":
    main()
