"""Visualization: a multi-panel summary + a sagittal stick-figure animation.

Візуалізація сесії: зведена панель (кути суглобів, активації, амплітуди
стимуляції після safety, GRF, фаза ходи) і анімація фігурки-палички у
сагітальній площині. matplotlib імпортується лише тут (опційна залежність).

Кожен графік логічно відповідає «доказу концепту» з канону §8: намір → фази →
активації → стим-команди (до/після safety) → сенсори.
"""

from __future__ import annotations

import math
import os

from ..biomech.kinematic import FOOT_LEN, HIP_HEIGHT, SHANK_LEN, THIGH_LEN
from ..runtime import Recorder

KEY_GROUPS = [
    "L_hip_flex",
    "L_knee_flex",
    "L_ankle_dorsi",
    "R_hip_flex",
    "R_knee_flex",
    "R_ankle_dorsi",
]


def _leg_points(hip_xy, hip_deg, knee_deg, ankle_deg):
    """Return (hip, knee, ankle, toe) points for one leg in the sagittal plane.

    Flexion is positive; the leg hangs down from the hip. Hip flexion swings the
    thigh forward (+x), knee flexion bends the shank back relative to the thigh.
    """
    hx, hy = hip_xy
    h = math.radians(hip_deg)
    knee = (hx + THIGH_LEN * math.sin(h), hy - THIGH_LEN * math.cos(h))
    shank_angle = h - math.radians(knee_deg)
    ankle = (
        knee[0] + SHANK_LEN * math.sin(shank_angle),
        knee[1] - SHANK_LEN * math.cos(shank_angle),
    )
    foot_angle = shank_angle + math.radians(90 + ankle_deg)
    toe = (
        ankle[0] + FOOT_LEN * math.sin(foot_angle),
        ankle[1] - FOOT_LEN * math.cos(foot_angle),
    )
    return (hx, hy), knee, ankle, toe


def save_summary(rec: Recorder, path: str, title: str = "BSO session") -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = rec.t
    fig, ax = plt.subplots(4, 1, figsize=(11, 12), sharex=True)
    fig.suptitle(f"{title}\n[RESEARCH SIMULATION — ILLUSTRATIVE values, not clinical]", fontsize=12)

    # 1) joint angles
    for k, c in (("L_hip", "tab:blue"), ("L_knee", "tab:cyan"), ("R_hip", "tab:red"),
                 ("R_knee", "tab:orange")):
        ax[0].plot(t, [p[k] for p in rec.pose], label=k, color=c, lw=1.2)
    ax[0].set_ylabel("joint angle (deg)")
    ax[0].legend(ncol=4, fontsize=8)
    ax[0].set_title("Kinematics (Layer 2 plant)")

    # 2) desired activations (Layer 1 output)
    for g in KEY_GROUPS:
        ax[1].plot(t, [a.get(g, 0.0) for a in rec.activations], label=g, lw=1.0)
    ax[1].set_ylabel("achieved activation")
    ax[1].legend(ncol=3, fontsize=7)
    ax[1].set_title("Muscle-group activation (post-safety, Layer 2→5)")

    # 3) stim amplitudes after safety
    def amp_for(applied, ch):
        for c in applied:
            if c.channel_id == ch:
                return c.amplitude_mA
        return 0.0

    for g in ("L_hip_flex", "L_knee_flex", "R_hip_flex", "R_knee_flex"):
        ch = f"ch_{g}"
        ax[2].plot(t, [amp_for(ap, ch) for ap in rec.applied], label=ch, lw=1.0)
    ax[2].set_ylabel("stim amplitude (mA)\nILLUSTRATIVE")
    ax[2].legend(ncol=2, fontsize=7)
    ax[2].set_title("Stimulation after Safety Supervisor (Layer 5)")

    # 4) GRF + balance
    ax[3].plot(t, [f.grf["L"] if f else 0 for f in rec.frames], label="GRF L", color="tab:blue")
    ax[3].plot(t, [f.grf["R"] if f else 0 for f in rec.frames], label="GRF R", color="tab:red")
    ax[3].set_ylabel("GRF (N)")
    ax[3].set_xlabel("time (s)")
    ax[3].legend(ncol=2, fontsize=8)
    ax[3].set_title("Ground reaction force (Layer 3 sensing)")

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def _clearance_series(rec: Recorder, win_s: float = 2.0, dt: float = 0.005):
    """Peak left-foot clearance (max-min foot height) per window — the foot-drag
    proxy. Returns (times, clearances)."""
    import numpy as np

    fy = np.array([p["L_foot_y"] for p in rec.pose])
    n = max(1, int(win_s / dt))
    ts, cs = [], []
    for i in range(n, len(fy), n):
        ts.append(rec.t[i])
        cs.append(float(fy[i - n : i].max() - fy[i - n : i].min()))
    return ts, cs


def save_resilience(recs: dict, path: str, title: str = "Adaptive resilience") -> str:
    """Compare conditions (nominal / degraded / degraded+adapt). ``recs`` maps a
    label -> Recorder. Plots foot clearance over time, fatigue, and adaptive
    gains — the proof that the Layer-4 adaptation compensates degradation."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
    fig.suptitle(f"{title}\n[RESEARCH SIMULATION — ILLUSTRATIVE values]", fontsize=12)

    for label, rec in recs.items():
        ts, cs = _clearance_series(rec)
        ax[0].plot(ts, cs, label=label, lw=1.8)
    ax[0].set_ylabel("foot clearance (m)\n(higher = no drag)")
    ax[0].set_title("Swing-foot clearance over the session — foot-drag proxy")
    ax[0].legend(fontsize=9)
    ax[0].grid(alpha=0.3)

    for label, rec in recs.items():
        if any(rec.fatigue):
            fat = [f.get("L_knee_flex", 0.0) for f in rec.fatigue]
            ax[1].plot(rec.t, fat, label=label, lw=1.2)
    ax[1].set_ylabel("fatigue level\n(L_knee_flex)")
    ax[1].set_title("Accumulated fatigue (plant degradation)")
    ax[1].legend(fontsize=9)
    ax[1].grid(alpha=0.3)

    for label, rec in recs.items():
        gains = [g.get("L_knee_flex", 1.0) for g in rec.gains]
        if max(gains) > 1.001:
            ax[2].plot(rec.t, gains, label=f"{label}: knee_flex", lw=1.2)
            ax[2].plot(rec.t, [g.get("L_hip_flex", 1.0) for g in rec.gains],
                       label=f"{label}: hip_flex", lw=1.0, ls="--")
    ax[2].set_ylabel("effector amplitude gain\n(Layer-4 adaptation)")
    ax[2].set_xlabel("time (s)")
    ax[2].set_title("Adaptive compensation gains (safety still clamps the result)")
    ax[2].legend(fontsize=8)
    ax[2].grid(alpha=0.3)

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def save_animation(rec: Recorder, path: str, stride: int = 8, fps: int = 25,
                   title: str = "BSO gait") -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter

    frames = list(range(0, len(rec.pose), stride))
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_xlim(-0.9, 0.9)
    ax.set_ylim(-0.1, 1.5)
    ax.set_aspect("equal")
    ax.axhline(0.0, color="0.6", lw=1)
    ax.set_title(f"{title}  [SIMULATION]")
    (lline,) = ax.plot([], [], "o-", color="tab:blue", lw=3, label="left")
    (rline,) = ax.plot([], [], "o-", color="tab:red", lw=3, label="right")
    (trunk,) = ax.plot([], [], "o-", color="0.2", lw=4)
    txt = ax.text(-0.85, 1.4, "", fontsize=9)
    ax.legend(loc="upper right", fontsize=8)

    def draw(i):
        idx = frames[i]
        p = rec.pose[idx]
        # Follow the real pelvis when a physics backend provides it (MuJoCo);
        # otherwise draw at a fixed hip (kinematic, walks in place).
        hip = (p.get("pelvis_x", 0.0), p.get("pelvis_z", HIP_HEIGHT))
        # trunk leans by trunk tilt
        tr = math.radians(p.get("trunk", 0.0))
        head = (hip[0] + 0.6 * math.sin(tr), hip[1] + 0.6 * math.cos(tr))
        trunk.set_data([hip[0], head[0]], [hip[1], head[1]])
        for side, line in (("L", lline), ("R", rline)):
            h, k, a, toe = _leg_points(hip, p[f"{side}_hip"], p[f"{side}_knee"],
                                       p[f"{side}_ankle"])
            line.set_data([h[0], k[0], a[0], toe[0]], [h[1], k[1], a[1], toe[1]])
        gp = rec.gait_phase[idx] or {}
        txt.set_text(f"t={rec.t[idx]:.2f}s  cadence={gp.get('cadence', 0):.0f}/min")
        return lline, rline, trunk, txt

    anim = FuncAnimation(fig, draw, frames=len(frames), blit=True, interval=1000 / fps)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    anim.save(path, writer=PillowWriter(fps=fps))
    plt.close(fig)
    return path
