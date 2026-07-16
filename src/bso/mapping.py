"""Automatic electrode→muscle mapping — what clinics now do by hand.

Автоматичний мапінг масиву електродів. У клініці (напр. the clinical partner з the partner stimulator,
16 контактів) лікар ГОДИНАМИ вручну перебирає контакти/амплітуди й дивиться, який
м'яз відповідає, будуючи мапу «контакт → м'яз». Цей модуль робить це АВТОМАТИЧНО:
агент пробує кожен контакт рампою амплітуди, зчитує (симульовані) відповіді м'язів,
оцінює поріг і вектор рекрутингу кожного контакту, будує мапу й обирає оптимальні
контакти під кожну рухову ціль.

Це навмисна модель феномену current spread уздовж масиву (контакт активує переважно
сусідні за положенням групи). Усе ILLUSTRATIVE. Реальні відповіді приходили б із
телеметрії/EMG стимулятора — архітектура від цього не змінюється.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

# 12 lower-limb muscle groups (exclude trunk), ordered rostro-caudal per side.
GROUPS = [
    "L_hip_flex", "L_hip_ext", "L_knee_flex", "L_knee_ext", "L_ankle_dorsi", "L_ankle_plantar",
    "R_hip_flex", "R_hip_ext", "R_knee_flex", "R_knee_ext", "R_ankle_dorsi", "R_ankle_plantar",
]


def _recruit(eff_amp: float, i50: float = 3.0, k: float = 1.4, thr: float = 0.8) -> float:
    if eff_amp <= thr:
        return 0.0
    a = 1.0 / (1.0 + math.exp(-k * (eff_amp - i50)))
    a0 = 1.0 / (1.0 + math.exp(-k * (thr - i50)))
    return max(0.0, min(1.0, (a - a0) / (1.0 - a0)))


@dataclass
class ElectrodeArray:
    """16-contact array with a (hidden) ground-truth recruitment matrix.

    Contacts 0..7 are on the left, 8..15 on the right. Each muscle group sits at a
    rostro-caudal location; a contact recruits a group by spatial proximity
    (current spread), strongly same-side and weakly across.
    """

    n_contacts: int = 16
    spread: float = 1.1
    cross_side: float = 0.15
    seed: int = 0
    W: np.ndarray = field(default=None)  # type: ignore[assignment]

    jitter: float = 0.0  # per-patient anatomical variation (for cohort studies)

    def __post_init__(self) -> None:
        # group locations: 6 per side spaced along that side's 8 contacts
        side_locs = np.array([0.5, 1.5, 3.0, 4.0, 5.5, 6.5])
        rng = np.random.default_rng(self.seed)
        loc = {}
        for i, g in enumerate(GROUPS):
            base = side_locs[i % 6]
            j = float(rng.normal(0, self.jitter)) if self.jitter else 0.0
            loc[g] = base + (0 if g.startswith("L") else 8) + j
        W = np.zeros((self.n_contacts, len(GROUPS)))
        for c in range(self.n_contacts):
            c_side_left = c < 8
            for gi, g in enumerate(GROUPS):
                g_left = g.startswith("L")
                same = (c_side_left == g_left)
                w = math.exp(-((c - loc[g]) / self.spread) ** 2)
                W[c, gi] = w * (1.0 if same else self.cross_side)
        self.W = W

    def stimulate(self, contact: int, amplitude: float, rng=None) -> np.ndarray:
        """Observed muscle-group response vector (0..1 each) for one contact at one
        amplitude — the (noisy) EMG-like reading the clinician would watch."""
        resp = np.array([_recruit(amplitude * self.W[contact, gi]) for gi in range(len(GROUPS))])
        if rng is not None:
            resp = np.clip(resp + rng.normal(0, 0.02, size=resp.shape), 0.0, 1.0)
        return resp


def auto_map(array: ElectrodeArray, amp_steps=(2.0, 4.0, 6.0, 8.0), seed: int = 1):
    """Probe every contact across an amplitude ramp; estimate the recruitment map
    and per-contact motor threshold. Returns (W_hat, thresholds, n_trials)."""
    rng = np.random.default_rng(seed)
    n = array.n_contacts
    W_hat = np.zeros((n, len(GROUPS)))
    thresholds = np.full(n, np.nan)
    trials = 0
    for c in range(n):
        for amp in amp_steps:
            resp = array.stimulate(c, amp, rng)
            trials += 1
            W_hat[c] = np.maximum(W_hat[c], resp)  # strongest response seen = weight proxy
            if np.isnan(thresholds[c]) and resp.max() > 0.1:
                thresholds[c] = amp
    return W_hat, thresholds, trials


def best_contact_per_group(W: np.ndarray) -> dict[str, int]:
    return {GROUPS[gi]: int(np.argmax(W[:, gi])) for gi in range(len(GROUPS))}


def mapping_accuracy(W_hat: np.ndarray, W_true: np.ndarray) -> float:
    """Fraction of groups whose best contact is correctly identified."""
    truth = best_contact_per_group(W_true)
    est = best_contact_per_group(W_hat)
    return sum(truth[g] == est[g] for g in GROUPS) / len(GROUPS)


def selectivity(W: np.ndarray, contact: int, group_index: int) -> float:
    """On-target vs total recruitment for a chosen contact (1.0 = perfectly
    selective)."""
    row = W[contact]
    total = row.sum()
    return float(row[group_index] / total) if total > 1e-9 else 0.0
