"""Live clinical advisor — turns a stream of decoded state into recommendations.

Core of the live AI layer: takes the current state (decoded intent + confidence,
signal sparing, bladder pressure, BP trend) and returns STRUCTURED advice for the
clinician/therapist — shown live while the patient trains. Deterministic clinical
rules (not a black box) — every piece of advice carries a reason and a priority.

Bilingual: English (default) with Ukrainian via lang="ua". It ADVISES — device
settings and clinical decisions stay with the clinician. Thresholds are illustrative.
"""

from __future__ import annotations

from dataclasses import dataclass

# severity drives ordering and colour in the UI
P0, P1, P2 = "P0", "P1", "P2"


@dataclass
class Advice:
    priority: str          # P0 (act now) / P1 (attention) / P2 (info)
    title: str
    why: str               # the reason — so the clinician can trust/override it

    def as_dict(self) -> dict:
        return {"priority": self.priority, "title": self.title, "why": self.why}


# clinical thresholds (illustrative)
BLADDER_DANGER_CMH2O = 40.0      # the upper-tract criterion — sustained detrusor pressure above this risks kidneys
AD_BP_RISE_WARN = 20.0           # systolic rise that flags autonomic dysreflexia onset
INTENT_CONF_OK = 0.75            # decode confidence we trust enough to enable stim
SPARING_WEAK = 0.45             # below this the residual signal is too noisy to rely on


def _program_for(intent: str, lang: str = "en") -> str:
    """Name Igor's real the device partner program for a decoded intent (with parameters)."""
    try:
        from .stim_programs import recommend
        p = recommend(intent)
        if p is None:
            return "No matching program in the map." if lang == "en" \
                else "Підходящої програми в карті немає."
        params = (f"PW {p.pw_us[0]:.0f}–{p.pw_us[1]:.0f}µs, "
                  f"{p.rate_hz[0]:.0f}–{p.rate_hz[1]:.0f}Hz, "
                  f"amp {p.amp[0]:.0f}–{p.amp[1]:.0f}")
        if lang == "en":
            return f"Recommended program: {p.slot} «{p.label}» ({params}). Clinician selects."
        return f"Рекомендована програма: {p.slot} «{p.label}» ({params}). Обирає лікар."
    except Exception:
        return ("Deliver a locomotor/postural pattern (clinician selects)." if lang == "en"
                else "Подати локомоторний/постуральний патерн (програму обирає лікар).")


def assess(state: dict, lang: str = "en") -> list[Advice]:
    """state keys (all optional): intent, intent_conf, sparing, bladder_pressure,
    ad_bp_rise, walk_recall. Returns advice sorted by priority (P0 first)."""
    out: list[Advice] = []
    en = lang != "ua"

    bp_rise = state.get("ad_bp_rise")
    if bp_rise is not None and bp_rise >= AD_BP_RISE_WARN:
        out.append(Advice(P0,
            "Autonomic dysreflexia risk — act now" if en
            else "Ризик автономної дисрефлексії — діяти зараз",
            (f"Systolic BP rising +{bp_rise:.0f} mmHg by trend. Check the trigger "
             "(bladder/bowel), sit the patient upright; the guardian has already "
             "lowered the stim drive.") if en else
            (f"Систолічний тиск росте на +{bp_rise:.0f} мм рт.ст. за трендом. "
             "Перевірити подразник (міхур/кишківник), посадити вертикально, "
             "вартовий уже знизив стим-драйв.")))

    bp = state.get("bladder_pressure")
    if bp is not None and bp >= BLADDER_DANGER_CMH2O:
        out.append(Advice(P0,
            "Detrusor pressure above safe limit" if en
            else "Тиск детрузора вище безпечного",
            (f"Detrusor {bp:.0f} cmH₂O > {BLADDER_DANGER_CMH2O:.0f} (the upper-tract criterion). Start "
             "coordinated voiding / catheterization to protect the kidneys.") if en else
            (f"Детрузор {bp:.0f} cmH₂O > {BLADDER_DANGER_CMH2O:.0f} (the upper-tract criterion). "
             "Запустити координоване спорожнення / катетеризацію, щоб берегти нирки.")))

    sparing = state.get("sparing")
    if sparing is not None and sparing < SPARING_WEAK:
        out.append(Advice(P1,
            "Residual signal is weak" if en else "Залишковий сигнал слабкий",
            (f"Signal sparing {sparing:.2f} < {SPARING_WEAK:.2f}. Add/move an sEMG "
             "electrode or widen the smoothing window — the intent decoder lacks "
             "signal.") if en else
            (f"Збереженість сигналу {sparing:.2f} < {SPARING_WEAK:.2f}. "
             "Додати/перемістити sEMG-електрод або зрости вікно згладжування — "
             "декодеру наміру бракує сигналу.")))

    intent = state.get("intent")
    conf = state.get("intent_conf")
    if intent and conf is not None:
        if conf >= INTENT_CONF_OK:
            prog = _program_for(intent, lang)
            if intent == "walk":
                out.append(Advice(P2,
                    "Confident «walk» intent — locomotion can be enabled" if en
                    else "Намір «йти» впевнений — локомоцію можна вмикати",
                    (f"Decoded WALK with {conf:.0%} confidence. {prog}") if en
                    else f"Декодовано WALK із впевненістю {conf:.0%}. {prog}"))
            elif intent == "stand":
                out.append(Advice(P2,
                    "«Stand» intent — hold posture" if en
                    else "Намір «стояти» — тримати поставу",
                    (f"Decoded STAND ({conf:.0%}). {prog}") if en
                    else f"Декодовано STAND ({conf:.0%}). {prog}"))
        else:
            out.append(Advice(P1,
                "Ambiguous intent — do not enable locomotion" if en
                else "Намір неоднозначний — не вмикати локомоцію",
                (f"Best class «{intent}» only {conf:.0%} < {INTENT_CONF_OK:.0%}. "
                 "Wait for a clearer intent to avoid a false step.") if en else
                (f"Найкращий клас «{intent}» лише {conf:.0%} < {INTENT_CONF_OK:.0%}. "
                 "Зачекати чіткіший намір, щоб не дати хибний крок.")))

    if not out:
        out.append(Advice(P2,
            "State is normal" if en else "Стан у нормі",
            "No dangerous trends; intent/pressure within safe bounds." if en
            else "Жодних небезпечних трендів; намір/тиск у безпечних межах."))

    order = {P0: 0, P1: 1, P2: 2}
    return sorted(out, key=lambda a: order[a.priority])
