"""Reflex as amplifier — let the living spinal loop do the standing (invention #6).

Винахід ІЗАР: нижче травми Th5-Th6 рефлекторна дуга ЖИВА (мотонейрони, аференти,
інтернейрони). Замість дорого «малювати» опору струмом, EES може підняти ПІДСИЛЕННЯ
власної петлі «навантаження→розгинання»: тоді МАЛИЙ центральний намір через живий
рефлекс дає ПОВНУ опору для стояння. EES тут — не привід м'яза, а регулятор
підсилення петлі.

Але петля має затримку (рефлекторна латентність), тож надто високе підсилення дає
КЛОНУС (коливання) — небезпечно. Отже існує ВІКНО: достатньо, щоб тримати вагу;
недостатньо, щоб зірватись у клонус.

Модель (ILLUSTRATIVE): затримана петля зворотного звʼязку по навантаженню
a_next = clamp(central + gain·(W − a_delayed)); W — вага, що її треба тримати.
"""

from __future__ import annotations

CENTRAL = 0.1        # small voluntary/EES central drive (the "intent")
W_LOAD = 0.7         # load to bear (normalized)
DELAY = 10           # reflex latency in ticks
REQ_SUPPORT = 0.35   # extensor support needed to bear weight (not buckle)
CLONUS_PP = 0.06     # steady-state peak-to-peak above this = clonus (unstable)
N = 800


def reflex_run(gain: float, central: float = CENTRAL) -> dict:
    """Run the delayed load-reflex loop at a given loop gain."""
    a = [0.0]
    hist = []
    for _ in range(N):
        a_del = a[-DELAY] if len(a) >= DELAY else 0.0
        nxt = max(0.0, min(1.0, central + gain * (W_LOAD - a_del)))
        a.append(nxt)
        hist.append(nxt)
    tail = hist[-160:]
    support = sum(tail) / len(tail)
    pp = max(tail) - min(tail)
    weight_bearing = support >= REQ_SUPPORT
    stable = pp < CLONUS_PP
    return {"gain": round(gain, 3), "support": round(support, 3),
            "clonus_pp": round(pp, 3), "weight_bearing": weight_bearing,
            "stable": stable, "ok": weight_bearing and stable}


def sweep(central: float = CENTRAL) -> dict:
    gains = [round(0.1 * i, 2) for i in range(0, 16)]
    rows = [reflex_run(g, central) for g in gains]
    window = [r["gain"] for r in rows if r["ok"]]
    return {
        "central": central,
        "req_support": REQ_SUPPORT,
        "rows": rows,
        "window": (min(window), max(window)) if window else None,
        "amplification": round(reflex_run(window[-1] if window else 0.9, central)["support"]
                               / max(central, 1e-6), 2),
    }
