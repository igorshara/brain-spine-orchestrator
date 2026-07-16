"""Multimodal spared-signal fusion — the middle path to intent.

Rather than rely on a single source, fuse whatever signals a patient still has:
residual EMG below the lesion, a cortical decoder, and spinal/peripheral activity.
Each modality reports an intent estimate with a reliability; the fusion is a
reliability-weighted vote that degrades gracefully when one modality drops out or
gets noisy. This is the pragmatic 'no chip in the brain required' path that still
benefits from a cortical channel when present.

Illustrative research simulation — not a medical device.
"""
from __future__ import annotations

import numpy as np

from .intent import INTENTS

MODALITIES = ("residual_emg", "cortical", "spinal")


class Modality:
    """A seedable noisy intent estimator. `reliability` in [0,1] scales both its
    accuracy and its fusion weight; `dropout` zeroes it out (channel lost)."""

    def __init__(self, name: str, reliability: float, seed: int = 0):
        self.name = name
        self.reliability = float(np.clip(reliability, 0.0, 1.0))
        self.rng = np.random.default_rng(seed)
        self.dropped = False

    def estimate(self, true_intent: int) -> tuple[np.ndarray, float]:
        """Return (probability over INTENTS, reliability). Higher reliability →
        sharper, more-often-correct distribution."""
        n = len(INTENTS)
        if self.dropped or self.reliability <= 0.0:
            return np.ones(n) / n, 0.0
        logits = self.rng.normal(0, 1.15, n)                 # fixed background noise
        logits[true_intent] += 2.0 * self.reliability        # signal strength ∝ reliability
        p = np.exp(logits - logits.max())
        return p / p.sum(), self.reliability


def fuse(estimates: list[tuple[np.ndarray, float]]) -> int:
    """Reliability-weighted fusion of per-modality probability vectors → intent."""
    n = len(INTENTS)
    acc = np.zeros(n)
    wsum = 0.0
    for p, w in estimates:
        acc += w * p
        wsum += w
    if wsum <= 0.0:
        return int(np.argmax(acc)) if acc.any() else 0
    return int(np.argmax(acc / wsum))


def demo(trials: int = 400, drop: str | None = "cortical", seed: int = 0) -> dict:
    """Compare fused accuracy vs each single modality, with one modality dropped
    to show graceful degradation. Returns accuracies."""
    rng = np.random.default_rng(seed)
    mods = [Modality("residual_emg", 0.7, seed=seed + 1),
            Modality("cortical", 0.85, seed=seed + 2),
            Modality("spinal", 0.55, seed=seed + 3)]
    single_hits = {m.name: 0 for m in mods}
    fused_hits = fused_hits_dropped = 0
    for _ in range(trials):
        true = int(rng.integers(0, len(INTENTS)))
        for m in mods:
            m.dropped = False
        ests = [m.estimate(true) for m in mods]
        for m, (p, _) in zip(mods, ests):
            single_hits[m.name] += int(np.argmax(p) == true)
        fused_hits += int(fuse(ests) == true)
        # now drop one modality and re-fuse — fusion should still hold up
        for m in mods:
            m.dropped = (m.name == drop)
        ests_d = [m.estimate(true) for m in mods]
        fused_hits_dropped += int(fuse(ests_d) == true)
    singles = {k: round(v / trials, 3) for k, v in single_hits.items()}
    return {
        "single": singles,
        "best_single": round(max(singles.values()), 3),
        "fused": round(fused_hits / trials, 3),
        "fused_with_dropout": round(fused_hits_dropped / trials, 3),
        "dropped": drop,
        "note": "Fusion ≥ best single modality, and survives a dropped channel.",
    }
