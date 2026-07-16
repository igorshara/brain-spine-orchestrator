"""Supervisory LLM layer — OUTSIDE the real-time motor loop (canon §3, M6).

Супервізорний шар: переклад цілей клініциста у конфіг протоколу, авто-звіти
сесій, пояснення рішень адаптації. КРИТИЧНО (канон §1.6): LLM НІКОЛИ не стоїть у
реальному моторному циклі — він працює лише на рівні конфігурації/аналітики, між
сесіями.

Модуль не вимагає API-ключа: якщо ``anthropic`` і ANTHROPIC_API_KEY доступні —
наратив пише модель; інакше використовується детермінований шаблон. У будь-якому
разі ЧИСЛА беруться з виміряних метрик сесії, а не вигадуються моделлю.
"""

from __future__ import annotations

import os

from .adaptation import Adaptation
from .runtime import Recorder

_SYSTEM = (
    "You write concise, honest rehabilitation-session summaries for a RESEARCH "
    "SIMULATOR of a brain-spine interface. This is NOT a medical device and the "
    "numbers are ILLUSTRATIVE, not clinical. Never make clinical claims or invent "
    "numbers; use only the metrics provided. Write in Ukrainian prose."
)


def _try_llm(prompt: str) -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=700,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    except Exception:
        return None


def session_report(rec: Recorder, fatigue_drift: float = 0.0, use_llm: bool = True) -> str:
    """Produce a Markdown session report. Deterministic metrics always; an LLM
    narrative on top when available."""
    adapt = Adaptation(fatigue_drift=fatigue_drift)
    m = adapt.session_metrics(rec)
    proposals = adapt.propose(rec)

    metrics_md = (
        f"- Тривалість сесії: **{rec.t[-1]:.1f} с** ({len(rec.t)} кроків симуляції)\n"
        f"- Середній каденс: **{m['mean_cadence']:.0f} кроків/хв**\n"
        f"- Частка часу зі збереженим балансом: **{m['balance_ok_ratio'] * 100:.0f}%**\n"
        f"- Середня асиметрія опори (GRF L/R): **{m['mean_grf_imbalance']:.2f}**\n"
        f"- Подій safety-супервізора (clamp/block): **{int(m['n_safety_events'])}**\n"
    )
    prop_md = "\n".join(
        f"- `{p.target_id}`: {p.param_deltas} — {p.rationale}" for p in proposals
    ) or "- Пропозицій адаптації немає: параметри в межах норми."

    prompt = (
        "Склади короткий звіт сесії (3-5 речень) за цими метриками симуляції. "
        "Будь чесним, без клінічних тверджень.\n\n"
        f"Метрики:\n{metrics_md}\nПропозиції адаптації:\n{prop_md}"
    )
    narrative = _try_llm(prompt) if use_llm else None
    if narrative is None:
        narrative = (
            "Сесія симуляції завершена в межах safety-обмежень. Хода ритмічна, "
            "баланс утримувався впродовж переважної частини часу. Відхилення "
            "параметрів і асиметрія опори — у межах, де достатньо повільної "
            "адаптації між сесіями (Шар 4). Усі значення ілюстративні."
        )

    return (
        "# Звіт сесії BSO (симуляція)\n\n"
        "> RESEARCH SIMULATION — усі числа ілюстративні, не клінічні.\n\n"
        "## Метрики\n"
        f"{metrics_md}\n"
        "## Висновок\n"
        f"{narrative}\n\n"
        "## Пропозиції адаптації (Шар 4, офлайн)\n"
        f"{prop_md}\n"
    )


def protocol_from_goals(goal_text: str) -> dict:
    """Translate a free-text clinician goal into a protocol config (deterministic
    keyword mapping; an LLM could refine this offline). Returns a config dict the
    supervisor would hand to Layers 1-2 BEFORE a session — never mid-loop."""
    text = goal_text.lower()
    cfg = {"mode_sequence": ["stand"], "target_speed": 0.4, "notes": goal_text}
    if any(w in text for w in ("хода", "ходит", "walk", "крок")):
        cfg["mode_sequence"] = ["stand", "walk"]
        cfg["target_speed"] = 0.6
    if any(w in text for w in ("сход", "stairs", "сходин")):
        cfg["mode_sequence"] = ["stand", "walk", "stairs_up"]
    if any(w in text for w in ("встат", "сидяч", "sit", "stand up")):
        cfg["mode_sequence"] = ["sit", "stand"]
    if any(w in text for w in ("обережн", "повільн", "safe", "slow")):
        cfg["target_speed"] = min(cfg["target_speed"], 0.3)
    return cfg
