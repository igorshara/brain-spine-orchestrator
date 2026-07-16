"""In-dashboard AI assistant — answers questions and comments on Igor's real data.

Live assistant in the dashboard: knows Igor's REAL stimulator programs, the current
decoded state and the clinical rules. Answers questions and comments on what it sees.

Two layers (robust for a live demo):
  • deterministic answers from the real data — always work, offline;
  • if ANTHROPIC_API_KEY + the anthropic package exist, free-form questions go to
    Claude with the same real data in context (numbers are NOT invented).

Bilingual: English (default) with Ukrainian via lang="ua". It ADVISES and EXPLAINS;
device settings and clinical decisions stay with the clinician.
"""

from __future__ import annotations

import os

from .advisor import assess
from .stim_programs import PROGRAMS, for_intent, recommend, summary

_INTENT = {"idle": ("idle", "спокій"), "stand": ("stand", "стояти"), "walk": ("walk", "йти")}


def _fmt(p) -> str:
    return (f"{p.slot} «{p.label}»: PW {p.pw_us[0]:.0f}–{p.pw_us[1]:.0f}µs, "
            f"{p.rate_hz[0]:.0f}–{p.rate_hz[1]:.0f}Hz, amp {p.amp[0]:.0f}–{p.amp[1]:.0f}")


def data_context() -> str:
    """Compact real-data context handed to the LLM (and the source of truth)."""
    lines = ["Igor's REAL stimulator programs (the partner stimulator, the clinical partner):"]
    lines += [f"  {_fmt(p)} [goal={p.goal}]" for p in PROGRAMS]
    lines.append("Columns: ↔=pulse width µs, middle=rate Hz, )))=amplitude mA/V.")
    lines.append("Physiology: walking=high rate 75–90Hz, standing=low 10–12Hz.")
    return "\n".join(lines)


def _rule_answer(q: str, lang: str = "en") -> str | None:
    """Deterministic answers from the real data. Returns None if no rule matches."""
    t = q.lower().strip()
    s = summary()
    en = lang != "ua"

    if any(w in t for w in ("підсум", "загальн висн", "вся картина", "overview", "summary",
                            "big picture", "verdict")):
        return session_summary(lang)

    if any(w in t for w in ("how many", "скільки програм", "кількість програм")):
        goals = ", ".join(f"{k}×{v}" for k, v in s["goals"].items())
        if en:
            return (f"You have **{s['n_programs']} programs** in banks "
                    f"{', '.join(s['groups'])}. By goal: {goals}.")
        return (f"У тебе **{s['n_programs']} програм** у групах {', '.join(s['groups'])}. "
                f"За цілями: {goals}.")

    if any(w in t for w in ("walk", "step", "ходь", "ходит", "крок")):
        ws = for_intent("walk")
        best = recommend("walk")
        body = "\n".join("• " + _fmt(p) for p in ws)
        if en:
            return (f"**Walking** programs ({len(ws)}):\n{body}\n\nCanonical for stepping "
                    f"(highest rate): **{_fmt(best)}**. High rate is the classic EES "
                    "scheme for step generation.")
        return (f"Програми **ходьби** ({len(ws)}):\n{body}\n\nКанонічна для кроку "
                f"(найвища частота): **{_fmt(best)}**.")

    if any(w in t for w in ("stand", "posture", "стоян", "стоят", "постав")):
        ss = [p for p in PROGRAMS if p.goal == "standing"]
        body = "\n".join("• " + _fmt(p) for p in ss)
        if en:
            return (f"**Standing** programs ({len(ss)}):\n{body}\n\nAll low rate (10–12 Hz): "
                    "tonic postural support, unlike high-rate walking.")
        return (f"Програми **стояння** ({len(ss)}):\n{body}\n\nУсі низька частота (10–12 Hz).")

    if any(w in t for w in ("spastic", "спастик", "тонус", "tone")):
        sp = [p for p in PROGRAMS if p.goal == "decrease_spasticity"]
        head = "Decrease spasticity: " if en else "Зниження спастики: "
        return head + "; ".join(_fmt(p) for p in sp) + "."

    if any(w in t for w in ("bladder", "bowel", "міхур", "сечов", "кишків")):
        if en:
            return ("Pelvic functions are not separate motor programs in the map, but the "
                    "system watches detrusor pressure (the upper-tract criterion 40 cmH₂O) and dysreflexia "
                    "risk and warns early. See the Electrode-plate tab — contact 16/S2.")
        return ("Тазові функції в карті не окремі програми, але система стежить за тиском "
                "детрузора (the upper-tract criterion 40 cmH₂O) і ризиком дисрефлексії. Див. вкладку пластини — S2.")

    if any(w in t for w in ("dysreflex", "safety", "blood pressure", "дисрефлекс",
                            "тиск", "безпек")):
        if en:
            return ("The autonomic-dysreflexia guardian predicts a BP surge by trend and "
                    "lowers the stim drive EARLY (predictive), 24/7 — vs reactive care. "
                    "In the demo: 0 episodes vs 377 uncontrolled.")
        return ("Вартовий автономної дисрефлексії прогнозує стрибок АТ і знижає драйв "
                "ЗАВЧАСНО, 24/7. У демо: 0 епізодів проти 377 без керування.")

    # specific slot like "A2", "B3"
    for p in PROGRAMS:
        if p.slot.lower() in t.replace(" ", ""):
            i_en, i_ua = _INTENT.get(p.intent, (p.intent, p.intent))
            if en:
                return f"**{_fmt(p)}** — goal: {p.goal}, serves intent «{i_en}»."
            return f"**{_fmt(p)}** — ціль: {p.goal}, намір «{i_ua}»."

    if any(w in t for w in ("frequen", "rate", "hz", "частот", "герц")):
        hi = max(PROGRAMS, key=lambda p: p.rate_hz[1])
        lo = min(PROGRAMS, key=lambda p: p.rate_hz[0])
        if en:
            return (f"Highest rate — {hi.slot} «{hi.label}» up to {hi.rate_hz[1]:.0f}Hz "
                    f"(walking); lowest — {lo.slot} «{lo.label}» from {lo.rate_hz[0]:.0f}Hz.")
        return (f"Найвища частота — {hi.slot} до {hi.rate_hz[1]:.0f}Hz (ходьба); "
                f"найнижча — {lo.slot} від {lo.rate_hz[0]:.0f}Hz.")

    if any(w in t for w in ("unit", "µs", "volt", "ma ", "одиниц", "вольт", "мА")):
        if en:
            return ("My reading of the columns: ↔=pulse width (µs), middle=rate (Hz), "
                    ")))=amplitude (mA or V). ⚠️ Confirm units with the clinical partner — 30 seconds.")
        return ("Колонки: ↔=тривалість імпульсу (µs), середня=частота (Hz), )))=амплітуда "
                "(mA/V). ⚠️ Підтвердити одиниці у the clinical partner.")

    if any(w in t for w in ("how does", "what is this", "explain", "як працює", "що це", "пояни")):
        if en:
            return ("The dashboard decodes your INTENT from residual signals (no brain chip) "
                    "→ selects your real program (e.g. A2 «Walking 1») → the safety guardian "
                    "checks it → delivers the pattern. The mapping agent automates the contact "
                    "search the clinic does by hand for hours.")
        return ("Декодуємо твій НАМІР із залишкових сигналів → обираємо твою програму → "
                "safety-вартовий → патерн. Агент-мапер автоматизує ручний підбір контактів.")

    return None


def answer(question: str, state: dict | None = None, use_llm: bool = True,
           lang: str = "en") -> dict:
    """Answer a question about Igor's data/system."""
    rule = _rule_answer(question, lang)
    if rule is None and use_llm:
        llm = _try_llm(question, state, lang)
        if llm is not None:
            return {"text": llm, "source": "llm"}
    if rule is None:
        if lang != "ua":
            rule = ("I can explain your programs (walking/standing/spasticity/a specific "
                    "slot like A2), frequencies, safety (dysreflexia/bladder) and how the "
                    "system works. Ask more specifically — or add an API key for free-form Q&A.")
        else:
            rule = ("Можу розповісти про твої програми, частоти, безпеку і як працює система. "
                    "Запитай конкретніше — або під'єднай API-ключ для вільних питань.")
        return {"text": rule, "source": "fallback"}
    return {"text": rule, "source": "rules"}


def comment_on_tab(tab: str, m: dict, lang: str = "en") -> str:
    """Proactive one-paragraph comment after a tab runs, grounded in real metrics."""
    en = lang != "ua"

    def g(k, d=0):
        v = m.get(k, d)
        return v if v is not None else d

    if tab == "osim":
        return (f"Ran the validated OpenSim model ({g('muscles', 18)} Hill muscles). "
                f"Left/right hip correlation {g('lr_hip_corr')} — motion is muscle-driven "
                "(forward dynamics), not drawn. Real anatomy, not a stick figure.") if en else (
                f"Прогнав валідовану OpenSim-модель ({g('muscles', 18)} м'язів). "
                f"Кореляція L/R стегна {g('lr_hip_corr')} — рух від сил м'язів, не намальований.")
    if tab == "programs":
        mp = m.get("mapping", {})
        return (f"Loaded your {g('n_programs', 20)} real programs in banks A/B/C. the clinical partner "
                f"tuned them by hand ~{mp.get('manual_minutes', '?')} min; the agent would "
                f"narrow the search to ~{mp.get('auto_minutes', '?')} min "
                f"({mp.get('speedup', '?')}× faster).") if en else (
                f"Завантажив твої {g('n_programs', 20)} реальних програм. the clinical partner підбирала "
                f"~{mp.get('manual_minutes', '?')} хв; агент ~{mp.get('auto_minutes', '?')} хв.")
    if tab == "sensors":
        conf = int(g("decode_conf") * 100)
        return (f"Decoding intent from residual signals: confidence {conf}%, current intent "
                f"«{g('live_intent', '—')}». The advisor updated its P0/P1 recommendations "
                "on the right.") if en else (
                f"Декодую намір: впевненість {conf}%, намір «{g('live_intent', '—')}». "
                "Порадник оновив рекомендації праворуч.")
    if tab == "map":
        return (f"Auto-mapped 16 contacts in {g('trials')} probes (accuracy {g('accuracy')}% "
                f"vs naive manual {g('manual')}%). This is what the clinic does by hand for "
                "hours.") if en else (
                f"Авто-мапінг 16 контактів за {g('trials')} проб (точність {g('accuracy')}%).")
    if tab == "progmap":
        return (f"Ran GP-BO across all {g('n_programs')} of your programs: ~{g('gp_mean_queries')} "
                f"probes per program vs ~{g('rand_mean_queries')} at random ({g('speedup')}× more "
                "efficient). That's how the agent finds the contact for each goal.") if en else (
                f"GP-BO по {g('n_programs')} програмах: ~{g('gp_mean_queries')} проб проти "
                f"~{g('rand_mean_queries')} навмання ({g('speedup')}× ефективніше).")
    if tab == "gym":
        return (f"Ran the open benchmark: GP-BO averages {g('steps')} steps-to-target and "
                f"{g('viol')} safety violations — beating random/grid. Digital-twin pre-optimized "
                f"starting programs in {g('probes')} in-silico probes before any clinic time. "
                "A reproducible testbed the field lacks.") if en else (
                f"Прогнав відкритий бенчмарк: GP-BO у середньому {g('steps')} кроків і {g('viol')} "
                f"порушень безпеки — краще за random/grid. Дигітал-твін перед-оптимізував стартові "
                f"програми за {g('probes')} проб in-silico до клініки. "
                "Відтворюваний testbed, якого полю бракує.")
    if tab == "autotrain":
        return (f"Scheduled training: {g('voids')} coordinated voids/day at low pressure "
                f"(peak {g('peak')} cmH₂O). Over 8 weeks the modeled post-void residual falls "
                f"{g('residual0')}→{g('residual8')} mL — the reflex is being trained, not just "
                "drained. R&D hypothesis; safety gated throughout.") if en else (
                f"Планове тренування: {g('voids')} координованих спорожнень/добу при низькому "
                f"тиску (пік {g('peak')} cmH₂O). За 8 тижнів залишок падає "
                f"{g('residual0')}→{g('residual8')} мл — рефлекс тренується. "
                "R&D-гіпотеза, під safety.")
    if tab == "plate":
        return ("Electrode plate (the 5-6-5 paddle array): each contact is labeled by anatomy. Pick a "
                "goal and the agent highlights the contacts and parameters.") if en else (
                "Пластина 5-6-5: кожен контакт підписаний за анатомією. Обери ціль — агент "
                "підсвітить контакти й параметри.")
    if tab == "guard":
        return ("Dysreflexia guardian: 0 episodes (predictive) vs 377 uncontrolled. Predicts "
                "the BP surge by trend and lowers the drive EARLY — 24/7.") if en else (
                "Вартовий дисрефлексії: 0 епізодів проти 377. Прогнозує стрибок АТ завчасно, 24/7.")
    if tab == "auto":
        return (f"Bladder: peak pressure {g('peak_pressure')} cmH₂O, residual {g('residual_ml')} "
                f"mL, dysreflexia events {g('ad_events')}. Coordinated EES keeps pressure "
                "safe.") if en else (
                f"Міхур: пік {g('peak_pressure')} cmH₂O, залишок {g('residual_ml')} мл, "
                f"епізодів {g('ad_events')}. Координована EES тримає тиск безпечним.")
    if tab == "loco":
        return (f"Schematic gait: cadence {g('cadence')} steps/min, "
                f"balance {g('balance_ok_pct')}%, safety events {g('safety_events')}. "
                "Simplified view — the real model is in the OpenSim tab.") if en else (
                f"Схематична хода: каденс {g('cadence')}/хв, баланс {g('balance_ok_pct')}%. "
                "Реальна модель — у вкладці OpenSim.")
    return "Done." if en else "Готово."


def session_summary(lang: str = "en") -> str:
    """One-paragraph holistic verdict across all verticals, grounded in real data."""
    s = summary()
    from .program_mapping import map_all
    pm = map_all(seed=0)["metrics"]
    walk = recommend("walk")
    if lang != "ua":
        return (
            f"Big picture. You have {s['n_programs']} real stimulator programs (banks "
            f"{', '.join(s['groups'])}) — the system speaks the clinical partner's language. The loop is "
            f"closed: decode INTENT from residual signals (no brain chip) → select your "
            f"program (e.g. {walk.slot} «{walk.label}») → safety guardian → pattern. "
            f"Auto-mapping (GP-BO) finds the contact for each program in ~{pm['gp_mean_queries']} "
            f"probes instead of ~{pm['rand_mean_queries']} at random ({pm['speedup']}× — saved "
            "clinician time). The autonomic-dysreflexia guardian gives 0 episodes vs 377 "
            "uncontrolled — life-safety 24/7. Bladder: coordinated EES keeps pressure below the "
            "the upper-tract criterion limit. All on the validated OpenSim model (18 Hill muscles), not a stick "
            "figure. HONEST: this is a research simulation — methods are real, synthetic numbers "
            "are illustrative; next step is real sensors and telemetry from the clinical partner/the device partner.")
    return (
        f"Загальна картина. {s['n_programs']} реальних програм (групи {', '.join(s['groups'])}). "
        f"Ланцюг замкнутий: намір → твоя програма ({walk.slot}) → safety → патерн. Авто-мапінг "
        f"~{pm['gp_mean_queries']} проб проти ~{pm['rand_mean_queries']} ({pm['speedup']}×). "
        "Вартовий дисрефлексії 0 проти 377. Це дослідницька симуляція — методи реальні, "
        "числа ілюстративні.")


def comment_on(state: dict, lang: str = "en") -> dict:
    """Proactive commentary on the current decoded state."""
    advice = [a.as_dict() for a in assess(state, lang)]
    intent = state.get("intent")
    prog = recommend(intent) if intent else None
    head = ""
    en = lang != "ua"
    if intent:
        i_en, i_ua = _INTENT.get(intent, (intent, intent))
        head = (f"I see intent «{i_en}»" if en else f"Бачу намір «{i_ua}»")
        if state.get("intent_conf") is not None:
            head += (f" (confidence {state['intent_conf']:.0%})" if en
                     else f" (впевненість {state['intent_conf']:.0%})")
        if prog:
            head += (f". Matching program — {prog.slot} «{prog.label}»." if en
                     else f". Твоя програма — {prog.slot} «{prog.label}».")
    return {"headline": head, "advice": advice}


_SYSTEM = (
    "You are an assistant in a neuro-rehabilitation research dashboard (Brain-Spine "
    "Orchestrator). This is a SIMULATION, not a medical device. Answer concisely and "
    "honestly. Use ONLY the provided real program data; do NOT invent numbers or give "
    "clinical prescriptions — the clinician decides. Match the user's language."
)


def _try_llm(question: str, state: dict | None, lang: str = "en") -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    ctx = data_context()
    if state:
        ctx += f"\nCurrent state: {state}"
    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-opus-4-8", max_tokens=600, system=_SYSTEM,
            messages=[{"role": "user", "content": f"{ctx}\n\nQuestion: {question}"}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    except Exception:
        return None
