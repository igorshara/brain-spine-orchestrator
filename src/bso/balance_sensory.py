"""Sensory closed loop — why restoring SENSATION is what keeps you standing.

Винахід ІЗАР #5: стояння — це обернений маятник. Щоб його втримати, мало знати
ПОЗИЦІЮ нахилу — треба відчувати ШВИДКІСТЬ хитання (пропріоцепцію), щоб гасити
падіння ДО того, як воно сталось. Після травми цей сигнал втрачено. Ідея:
повернути сенсорний контур (напр. електротактильне заміщення у збережену зону) =
повернути член швидкості в керування балансом.

Модель (ILLUSTRATIVE): нормований обернений маятник theta'' = a·sin(theta) − u.
Сенсорні режими керування u:
  - "off"            : сенсорики нема (u=0) — людина перекидається;
  - "reactive"       : лише позиція (u = Kp·theta) — недемпфована хитавиця, падає;
  - "proprioceptive" : позиція + швидкість (u = Kp·theta + Kd·omega) — гасить і стоїть.
Це фізіологічно: втрата пропріоцепції = сенсорна атаксія (проба Ромберга).
"""

from __future__ import annotations

import math

A_GRAVITY = 9.8        # destabilizing term of the inverted pendulum (g/L)
KP, KD = 18.0, 6.0     # position / velocity (proprioceptive) control gains
PUSH = 1.2             # perturbation impulse to angular velocity (rad/s)
FALL_RAD = 0.40        # |tilt| beyond this (~23 deg) counts as a fall
DT, DUR = 0.005, 12.0


def balance_run(mode: str, push: float = PUSH) -> dict:
    """Standing with scheduled lateral pushes under one sensory mode."""
    theta = omega = 0.0
    perturb = {round(1.5 + 1.5 * i, 3): push * (1 if i % 2 == 0 else -1) for i in range(7)}
    max_tilt = 0.0
    fell = False
    trace = []
    n = int(DUR / DT)
    for k in range(n):
        t = round(k * DT, 3)
        if t in perturb:
            omega += perturb[t]
        if mode == "off":
            u = 0.0
        elif mode == "reactive":
            u = KP * theta                       # position only — no rate sense
        else:                                    # proprioceptive
            u = KP * theta + KD * omega          # position + velocity (rate of sway)
        omega += DT * (A_GRAVITY * math.sin(theta) - u)
        theta += DT * omega
        max_tilt = max(max_tilt, abs(theta))
        if abs(theta) > FALL_RAD:
            fell = True
        if k % 12 == 0:
            trace.append({"t": t, "tilt_deg": round(math.degrees(theta), 2)})
    return {"mode": mode, "max_tilt_deg": round(math.degrees(max_tilt), 1),
            "fell": fell, "upright": not fell, "trace": trace}


def compare(push: float = PUSH) -> dict:
    modes = {m: balance_run(m, push) for m in ("off", "reactive", "proprioceptive")}
    return {"push": push, "fall_deg": round(math.degrees(FALL_RAD), 1),
            "modes": {m: {k: v for k, v in r.items() if k != "trace"}
                      for m, r in modes.items()},
            "traces": {m: r["trace"] for m, r in modes.items()}}
