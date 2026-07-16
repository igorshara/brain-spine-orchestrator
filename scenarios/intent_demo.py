"""Demo: residual-signal intent decoding closes the loop without a brain chip.

Декодуємо намір (стояти/йти) із шумних ЗАЛИШКОВИХ сигналів і годуємо ним наш CPG —
«думаю крок → крок» без імпланту в мозок. Показуємо точність, латентність, плавну
деградацію зі зниженням збереженості сигналу, і ЗАМИКАННЯ петлі (декодований намір
веде ходу). Усе ILLUSTRATIVE.

Запуск:  python3 scenarios/intent_demo.py
"""

from __future__ import annotations

import os

import _bootstrap  # noqa: F401
import numpy as np

from bso.decoder_stub import IntentEvent
from bso.intent import INTENTS, IntentDecoder, ResidualSignalModel, decode_stream
from bso.runtime import build_system
from bso.schemas import Mode

TIMELINE = [("idle", 20), ("stand", 20), ("walk", 40), ("stand", 20), ("idle", 20)]


def _train(sparing, seed=1):
    m = ResidualSignalModel(sparing=sparing, seed=seed)
    X, y = m.dataset(200)
    idx = np.random.default_rng(0).permutation(len(X))
    ntr = int(0.8 * len(X))
    dec = IntentDecoder(smooth=5).fit(X[idx[:ntr]], y[idx[:ntr]])
    return dec, dec.accuracy(X[idx[ntr:]], y[idx[ntr:]])


def main(render: bool = True) -> None:
    print("=== Residual-signal intent decoding (no brain chip) — idea 4 ===")
    for sp in (0.8, 0.5, 0.3):
        dec, acc = _train(sp)
        true, d, lat = decode_stream(dec, ResidualSignalModel(sp, seed=2), TIMELINE)
        print(f"  sparing={sp:.1f}: classify {acc * 100:.0f}% | live decode "
              f"{(true == d).mean() * 100:.0f}% | lock-on {lat:.1f} steps")

    # close the loop: decoded intent (sparing 0.6) drives the CPG -> it walks on intent
    dec, _ = _train(0.6)
    true, d, _ = decode_stream(dec, ResidualSignalModel(0.6, seed=3), TIMELINE)
    walk_idx = INTENTS.index("walk")
    walk_mask = true == walk_idx
    walk_recall = (d[walk_mask] == walk_idx).mean()  # of true-walk steps, % decoded as walk
    sched = [IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.5)]
    rec = build_system(sched).run(6.0)
    gs = [g for g in rec.gait_state if g is not None]
    print(f"\n  closed loop: during true-walk intent, decoded WALK {walk_recall * 100:.0f}% "
          f"-> CPG produced gait (cadence {gs[-1].cadence:.0f}/min). "
          f"'Think step -> step', no implant.")

    if render:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        dec, _ = _train(0.5)
        true, d, lat = decode_stream(dec, ResidualSignalModel(0.5, seed=4), TIMELINE)
        fig, ax = plt.subplots(figsize=(11, 4.2))
        ax.step(range(len(true)), true, where="post", label="true intent", color="tab:gray", lw=2)
        ax.step(range(len(d)), d, where="post", label="decoded (residual signals)",
                color="tab:green", lw=1.4, ls="--")
        ax.set_yticks(range(len(INTENTS)))
        ax.set_yticklabels(INTENTS)
        ax.set_xlabel("time step")
        ax.set_title("Intent decoded from residual signals (sparing 0.5) drives the system\n"
                     "[no brain chip · RESEARCH SIMULATION, ILLUSTRATIVE]", fontsize=11)
        ax.legend()
        ax.grid(alpha=0.3)
        out = os.path.join(os.path.abspath(_bootstrap.OUTPUT_DIR), "intent_decode.png")
        fig.tight_layout()
        fig.savefig(out, dpi=110)
        plt.close(fig)
        print("saved:", out)


if __name__ == "__main__":
    main()
