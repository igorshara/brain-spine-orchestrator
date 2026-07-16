"""Train a cross-speed gait policy with Evolution Strategies; test generalization.

Навчаємо speed-conditioned політику через ES на швидкостях [0.3,0.4,0.6,0.7] і
ПЕРЕВІРЯЄМО на відкладеній 0.5 (ніколи не тренованій). Порівнюємо з baseline без
політики. Якщо навчена політика на 0.5 краща за baseline — вона УЗАГАЛЬНИЛА (на
відміну від клонування Moco, яке не генералізувало). Усе ILLUSTRATIVE.

Запуск:  python3 scenarios/rl_train.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401
import numpy as np

from bso.rl_gait import GaitPolicy, es_train, rollout

TRAIN = [0.3, 0.4, 0.6, 0.7]
HELDOUT = 0.5


def main() -> None:
    print("=== Cross-speed gait policy via Evolution Strategies ===")
    base = GaitPolicy()  # zero params -> gain 1.0 -> no compensation (baseline)
    base_train = np.mean([rollout(base, s) for s in TRAIN])
    base_held = rollout(base, HELDOUT)
    print(f"  baseline (no policy): train-speeds reward={base_train:.3f}, "
          f"held-out {HELDOUT} reward={base_held:.3f}")

    print(f"  training ES on speeds {TRAIN} (~1 min)...")
    best, hist = es_train(TRAIN, pop=18, elite=5, iters=14, seed=0)
    pol = GaitPolicy(best)
    print(f"  ES reward curve (best so far): {[round(h, 3) for h in hist[::3]]}")

    tr = np.mean([rollout(pol, s) for s in TRAIN])
    held = rollout(pol, HELDOUT)
    print(f"\n  trained policy: train-speeds reward={tr:.3f}, "
          f"HELD-OUT {HELDOUT} reward={held:.3f}")
    gain = (held - base_held) / abs(base_held) * 100 if base_held else 0.0
    if held > base_held * 1.1:
        print(f"  -> GENERALIZES: on the unseen speed the policy beats baseline by "
              f"{gain:+.0f}% (direct policy optimization succeeds where cloning failed).")
    else:
        print(f"  -> honest: did not clearly beat baseline at the held-out speed "
              f"({gain:+.0f}%); needs more training/features.")

    out = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "rl_gait_policy.json")
    import json
    with open(out, "w") as f:
        json.dump({"params": best.tolist()}, f)
    print("  saved policy ->", out)


if __name__ == "__main__":
    main()
