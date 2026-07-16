"""Muscle-group <-> stimulation-channel map and recruitment curves.

Мапа м'язових груп на канали стимуляції + калібрувальні криві рекрутингу.
EES does not drive muscles directly; physiologically it recruits afferents and
engages spinal circuits. Here we model the *net* effect as a per-group
recruitment curve mapping stimulation amplitude -> normalized activation, which
is a deliberate simplification documented in the project canon.

All numbers ILLUSTRATIVE.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RecruitmentCurve:
    """Sigmoid recruitment: activation = 1 / (1 + exp(-k*(I - I50))).

    I50 — amplitude (mA) at half recruitment; k — steepness. ILLUSTRATIVE.
    """

    i50_mA: float = 3.0  # ILLUSTRATIVE half-activation amplitude
    k: float = 1.4  # ILLUSTRATIVE steepness
    threshold_mA: float = 0.8  # below this, no functional recruitment

    def activation(self, amplitude_mA: float) -> float:
        if amplitude_mA <= self.threshold_mA:
            return 0.0
        a = 1.0 / (1.0 + math.exp(-self.k * (amplitude_mA - self.i50_mA)))
        # Re-normalize so threshold maps to ~0 and saturation to ~1.
        a0 = 1.0 / (1.0 + math.exp(-self.k * (self.threshold_mA - self.i50_mA)))
        return max(0.0, min(1.0, (a - a0) / (1.0 - a0)))

    def primed(self, shift_mA: float) -> "RecruitmentCurve":
        """Return a curve shifted LEFT by subthreshold EES priming: the half-
        activation amplitude and threshold drop, so the same peripheral pulse
        recruits more (the spinal pool sits closer to firing). ILLUSTRATIVE."""
        s = max(0.0, shift_mA)
        return RecruitmentCurve(i50_mA=max(0.1, self.i50_mA - s),
                                k=self.k,
                                threshold_mA=max(0.0, self.threshold_mA - s))

    def amplitude_for(self, target_activation: float) -> float:
        """Inverse curve: amplitude needed for a target activation (0..1)."""
        a = max(0.0, min(0.999, target_activation))
        if a <= 0.0:
            return 0.0
        a0 = 1.0 / (1.0 + math.exp(-self.k * (self.threshold_mA - self.i50_mA)))
        raw = a * (1.0 - a0) + a0
        raw = min(max(raw, 1e-6), 1 - 1e-6)
        return self.i50_mA - math.log(1.0 / raw - 1.0) / self.k


@dataclass(frozen=True)
class MuscleGroup:
    group_id: str  # e.g. "L_hip_flex"
    side: str  # "L" / "R"
    joint: str  # "hip" / "knee" / "ankle" / "trunk"
    action: str  # "flex" / "ext" / "dorsi" / "plantar" / "stab"
    channel_id: str  # stimulation channel
    contacts: tuple[int, ...]  # active electrode contacts
    recruitment: RecruitmentCurve = field(default_factory=RecruitmentCurve)
    # Default stimulation shape for this group (ILLUSTRATIVE).
    default_pulse_width_us: float = 250.0
    default_frequency_Hz: float = 40.0


def _build_groups() -> dict[str, MuscleGroup]:
    groups: dict[str, MuscleGroup] = {}
    # joint -> (action_a, action_b)
    antagonist_pairs = {
        "hip": ("flex", "ext"),
        "knee": ("flex", "ext"),
        "ankle": ("dorsi", "plantar"),
    }
    contact = 0
    for side in ("L", "R"):
        for joint, (a, b) in antagonist_pairs.items():
            for action in (a, b):
                gid = f"{side}_{joint}_{action}"
                groups[gid] = MuscleGroup(
                    group_id=gid,
                    side=side,
                    joint=joint,
                    action=action,
                    channel_id=f"ch_{gid}",
                    contacts=(contact, contact + 1),
                )
                contact += 2
        # trunk stabilizer per side
        gid = f"{side}_trunk_stab"
        groups[gid] = MuscleGroup(
            group_id=gid,
            side=side,
            joint="trunk",
            action="stab",
            channel_id=f"ch_{gid}",
            contacts=(contact, contact + 1),
            default_frequency_Hz=30.0,
        )
        contact += 2
    return groups


MUSCLE_GROUPS: dict[str, MuscleGroup] = _build_groups()

# Convenience views.
GROUP_IDS: tuple[str, ...] = tuple(MUSCLE_GROUPS.keys())
CHANNEL_TO_GROUP: dict[str, str] = {g.channel_id: gid for gid, g in MUSCLE_GROUPS.items()}


def _build_antagonists() -> dict[str, str]:
    """Map each group to its same-joint, opposite-action antagonist (if any).
    Used to model current spread / co-activation between neighbouring contacts."""
    opp = {"flex": "ext", "ext": "flex", "dorsi": "plantar", "plantar": "dorsi"}
    out: dict[str, str] = {}
    for gid, g in MUSCLE_GROUPS.items():
        if g.action in opp:
            cand = f"{g.side}_{g.joint}_{opp[g.action]}"
            if cand in MUSCLE_GROUPS:
                out[gid] = cand
    return out


ANTAGONIST: dict[str, str] = _build_antagonists()
