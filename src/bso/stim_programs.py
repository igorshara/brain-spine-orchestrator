"""Igor's REAL the partner stimulator stimulation programs (the clinical partner, Bangkok).

Транскрипція справжньої таблиці програм стимулятора Ігоря (фото 2026-06-05). Це
перехід від синтетики до РЕАЛЬНИХ параметрів: кожна програма має функціональну ціль
і три параметри. Інтерпретація колонок (підтвердити у the clinical partner):
  pw_us   ↔  тривалість імпульсу, µs   (300–600)
  rate_hz ⏩ частота, Hz               (10–90)
  amp     )) амплітуда, mA або V       (4–16)

Фізіологія сходиться: ХОДЬБА = висока частота (75–90 Hz), СТОЯННЯ = низька (10–12 Hz)
— класична схема EES. Групи A/B/C — як the clinical partner згрупувала програми вручну (саме цей
ручний підбір ми й автоматизуємо).

Числа — діапазони, які підбирав клініцист; (lo, hi) зберігаємо як є.
"""

from __future__ import annotations

from dataclasses import dataclass

# functional goal -> which decoded INTENT it serves (intent.py: idle/stand/walk)
GOAL_TO_INTENT = {
    "trunk": "stand", "walking": "walk", "standing": "stand",
    "overnight": "idle", "decrease_spasticity": "idle",
    "pulling_up": "stand", "pushing": "stand",
}


def _rng(s: str) -> tuple[float, float]:
    """'550-600' -> (550,600); '75' -> (75,75)."""
    parts = s.replace("–", "-").split("-")
    vals = [float(p) for p in parts]
    return (vals[0], vals[-1])


@dataclass(frozen=True)
class Program:
    group: str          # A/B/C bank
    slot: str           # A1, B3, ...
    label: str          # clinician's name, e.g. "Walking 1"
    goal: str           # normalized functional goal (key of GOAL_TO_INTENT)
    pw_us: tuple        # pulse width range (µs)
    rate_hz: tuple      # frequency range (Hz)
    amp: tuple          # amplitude range (mA/V)

    @property
    def intent(self) -> str:
        return GOAL_TO_INTENT.get(self.goal, "idle")

    def mid(self) -> dict:
        return {"pw_us": sum(self.pw_us) / 2, "rate_hz": sum(self.rate_hz) / 2,
                "amp": sum(self.amp) / 2}

    def as_dict(self) -> dict:
        return {"slot": self.slot, "label": self.label, "goal": self.goal,
                "intent": self.intent, "pw_us": list(self.pw_us),
                "rate_hz": list(self.rate_hz), "amp": list(self.amp)}


def _p(group, slot, label, goal, pw, rate, amp):
    return Program(group, slot, label, goal, _rng(pw), _rng(rate), _rng(amp))


# --- exact transcription of Igor's program map ---
PROGRAMS: list[Program] = [
    # Group A
    _p("A", "A1", "Trunk", "trunk", "400", "75-85", "10.0-15.0"),
    _p("A", "A2", "Walking 1", "walking", "550-600", "85-90", "12.0-15.0"),
    _p("A", "A3", "Walking 1", "walking", "500-550", "18", "9.0-12.0"),
    _p("A", "A3", "Standing 1", "standing", "500-550", "10-12", "10.0-16.0"),
    _p("A", "A4", "Overnight/center stimulation", "overnight", "300", "14-15", "4.0-5.0"),
    # Group B
    _p("B", "B1", "Decrease spasticity", "decrease_spasticity", "300", "85-90", "9.0-12.0"),
    _p("B", "B2", "Walking 2", "walking", "500-600", "75", "12.0-14.0"),
    _p("B", "B2", "Both pulling up (sit)", "pulling_up", "500-600", "75-85", "11.0-14.0"),
    _p("B", "B3", "Walking 2", "walking", "300", "15", "8.0-10.0"),
    _p("B", "B3", "Standing 2", "standing", "300-350", "10-12", "13.0-16.0"),
    _p("B", "B3", "Left pushing 1 (sit)", "pushing", "300-350", "10-12", "7.0-9.0"),
    _p("B", "B4", "Walking 2", "walking", "350", "15", "8.0-10.0"),
    _p("B", "B4", "Standing 2", "standing", "300-350", "10-12", "13.0-16.0"),
    _p("B", "B4", "Right pushing 1 (sit)", "pushing", "300-350", "10-12", "7.0-9.0"),
    # Group C
    _p("C", "C1", "Left pulling up (sit)", "pulling_up", "550-600", "80-90", "12.0-16.0"),
    _p("C", "C2", "Right pulling up (sit)", "pulling_up", "500-600", "80-90", "12.0-16.0"),
    _p("C", "C3", "Standing 3", "standing", "350-400", "10-12", "8.0-15.0"),
    _p("C", "C3", "Left pushing 2 (sit)", "pushing", "350-400", "10-12", "8.0-10.0"),
    _p("C", "C4", "Standing 3", "standing", "350-400", "10-12", "8.0-15.0"),
    _p("C", "C4", "Right pushing 2 (sit)", "pushing", "350-400", "10-12", "8.0-10.0"),
]


def for_intent(intent: str) -> list[Program]:
    """All programs whose functional goal serves a decoded intent."""
    return [p for p in PROGRAMS if p.intent == intent]


def recommend(intent: str) -> Program | None:
    """Pick a representative program for a decoded intent. Walking -> the higher-
    frequency variant (the canonical stepping config); else the first match."""
    cands = for_intent(intent)
    if not cands:
        return None
    if intent == "walk":
        return max(cands, key=lambda p: p.rate_hz[1])  # highest-rate walking program
    return cands[0]


def summary() -> dict:
    goals: dict[str, int] = {}
    for p in PROGRAMS:
        goals[p.goal] = goals.get(p.goal, 0) + 1
    return {"n_programs": len(PROGRAMS), "groups": sorted({p.group for p in PROGRAMS}),
            "goals": goals}
