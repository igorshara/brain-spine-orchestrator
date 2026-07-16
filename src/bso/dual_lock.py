"""Dual lock — EES priming + selective peripheral execution (invention #4).

Винахід ІЗАР: один канал EES мусить і ЗБУДИТИ спинальну мережу, і ВИКОНАТИ рух —
конфлікт. Щоб дотягти слабкий контакт до руху, женуть амплітуду, ловлячи перелив
струму на антагоніст (co-activation), що З'ЇДАЄ чисту силу. Ідея: розділити ролі в
ПРОСТОРІ. EES тримає subthreshold «готовність» (priming зсуває криву рекрутингу
вліво), а дешевий СЕЛЕКТИВНИЙ периферійний стим конкретного м'яза додає рух БЕЗ
переливу. Жоден канал окремо не дає рух — разом дають, за менший заряд.

Модель (ILLUSTRATIVE): чиста сила = активація агоніста − coupling·активація
антагоніста. EES розливається на антагоніст (coupling), периферія — ні.
Заряд ~ амплітуда (однакова ширина імпульсу для чесності).
"""

from __future__ import annotations

from .config.muscles import RecruitmentCurve

PRIME_AMP_mA = 0.6      # subthreshold EES priming (below the 0.8 mA motor threshold)
PRIME_ALPHA = 1.5       # how far priming shifts the recruitment curve per mA


def single_ees(target_net: float, coupling: float,
               curve: RecruitmentCurve | None = None) -> dict | None:
    """One EES channel does both jobs. Current spread co-activates the antagonist,
    so net force = a·(1−coupling); you must over-drive the agonist to compensate."""
    curve = curve or RecruitmentCurve()
    denom = 1.0 - coupling
    a = target_net / denom if denom > 1e-6 else 1.0
    if a >= 0.999:
        return None                      # infeasible without exceeding saturation
    amp = curve.amplitude_for(a)
    return {"amp_ees": round(amp, 3), "charge": round(amp, 3),
            "spillover": round(coupling * a, 3), "net": round(a * (1 - coupling), 3)}


def dual_lock(target_net: float, prime_amp: float = PRIME_AMP_mA,
              alpha: float = PRIME_ALPHA, curve: RecruitmentCurve | None = None) -> dict:
    """Subthreshold EES priming shifts the curve left; a selective peripheral
    pulse executes with NO antagonist spillover. Total charge = priming + periph."""
    curve = curve or RecruitmentCurve()
    shift = alpha * prime_amp
    primed = curve.primed(shift)
    q = primed.amplitude_for(target_net)         # periphery hits the target directly
    return {"amp_prime": round(prime_amp, 3), "amp_periph": round(q, 3),
            "charge": round(prime_amp + q, 3), "spillover": 0.0,
            "net": round(target_net, 3)}


def compare(target_net: float = 0.5, coupling: float = 0.3) -> dict:
    s = single_ees(target_net, coupling)
    d = dual_lock(target_net)
    out = {"target_net": target_net, "coupling": coupling, "single": s, "dual": d}
    if s:
        out["charge_saving_pct"] = round(100.0 * (s["charge"] - d["charge"]) / s["charge"], 1)
        out["spillover_removed"] = round(s["spillover"], 3)
    return out
