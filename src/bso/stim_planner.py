"""Stim planner — the agent LEARNS the clinician's pattern from Igor's real
programs, then selects contacts + parameters for a goal.

«Навчити агента аналізувати й підбирати параметри». Робимо це чесно й даними:
  1. LEARN — з реальної таблиці програм виводимо закономірності клініциста
     (яка частота/тривалість/амплітуда типова під кожну ціль). Це не вигадка —
     статистика з його ж 20 програм.
  2. SELECT — для заданої цілі агент пропонує: (а) які КОНТАКТИ задіяти (анатомія
     паддла 5-6-5), (б) стартові ПАРАМЕТРИ (з вивчених правил), (в) ПЛАН доточнення
     амплітуди методом GP-BO (одиниці проб замість сотень).

Прилад завжди налаштовує лікар — агент лише радить обґрунтований старт і звужує пошук.
"""

from __future__ import annotations

import numpy as np

from .electrode_array import contacts_for_goal
from .stim_programs import GOAL_TO_INTENT, PROGRAMS


def learn_rules() -> dict:
    """Derive per-goal parameter patterns from the real program table (the agent
    'learning' the clinician's choices). Returns mean ranges + a plain-language note."""
    rules: dict[str, dict] = {}
    goals = sorted({p.goal for p in PROGRAMS})
    for g in goals:
        ps = [p for p in PROGRAMS if p.goal == g]
        pw = np.array([p.mid()["pw_us"] for p in ps])
        rate = np.array([p.mid()["rate_hz"] for p in ps])
        amp = np.array([p.mid()["amp"] for p in ps])
        rules[g] = {
            "n": len(ps),
            "pw_us": [round(float(pw.min())), round(float(pw.max()))],
            "rate_hz": [round(float(rate.min())), round(float(rate.max()))],
            "amp": [round(float(amp.min()), 1), round(float(amp.max()), 1)],
            "rate_mean": round(float(rate.mean()), 1),
        }
    return rules


def _frequency_insight(lang: str = "en") -> str:
    r = learn_rules()
    walk = r.get("walking", {}).get("rate_mean", 0)
    stand = r.get("standing", {}).get("rate_mean", 0)
    if walk and stand:
        if lang != "ua":
            return (f"Learned rule: walking ~{walk:.0f} Hz (high rate for stepping), "
                    f"standing ~{stand:.0f} Hz (low, tonic) — the classic EES scheme.")
        return (f"Вивчене правило: ходьба ~{walk:.0f} Hz, стояння ~{stand:.0f} Hz — "
                "класична EES-схема.")
    return ("Learned rule: rate depends on the goal (step=high, posture=low)." if lang != "ua"
            else "Вивчене правило: частота залежить від цілі (крок=висока, постава=низька).")


def recommend_parameters(goal: str, lang: str = "en") -> dict:
    """Full agent recommendation for a goal: contacts + starting parameters +
    a GP-BO amplitude-tuning plan. Deterministic, grounded in real data."""
    rules = learn_rules()
    rule = rules.get(goal)
    contacts = contacts_for_goal(goal)
    intent = GOAL_TO_INTENT.get(goal, "idle")
    en = lang != "ua"

    if rule is None:
        note = ("No direct programs for this goal in the table — start from a neighbouring goal."
                if en else "Немає прямих програм цієї цілі — старт від сусідньої цілі.")
        return {"goal": goal, "intent": intent, "contacts": [c.as_dict() for c in contacts],
                "note": note, "params": None}

    # amplitude tuning plan: GP-BO over the learned amplitude range (start low for safety)
    lo, hi = rule["amp"]
    n_steps = 6  # GP-BO typically needs only a handful of probes
    plan = {"sweep": "amplitude", "range": [lo, hi], "start": lo,
            "method": "GP-BO (Bonizzato 2023)", "expected_probes": n_steps,
            "vs_grid_probes": max(8, round((hi - lo) / 0.5))}

    note = ("Starting parameters come from your real programs for this goal; contacts from "
            "the paddle anatomy. Fine-tune amplitude with GP-BO. The clinician sets it." if en
            else "Стартові параметри — з твоїх реальних програм; контакти — з анатомії паддла. "
                 "Доточнити амплітуду GP-BO. Налаштовує лікар.")
    return {
        "goal": goal, "intent": intent,
        "contacts": [c.as_dict() for c in contacts],
        "params": {"pw_us": rule["pw_us"], "rate_hz": rule["rate_hz"], "amp": rule["amp"]},
        "tuning_plan": plan,
        "insight": _frequency_insight(lang),
        "note": note,
    }
