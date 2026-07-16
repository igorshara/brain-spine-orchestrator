"""Auto-mapping demo framed on Igor's REAL programs.

Для КОЖНОЇ з реальних програм Ігоря агент шукає в просторі 16 контактів той, що дає
найкращу селективність під її функціональну ціль — методом GP-BO (Bonizzato 2023),
а не перебором. Повертаємо послідовність запитів (для анімації звуження пошуку) і
порівняння з випадковим перебором.

Чесно: метод GP-BO — реальний; «правильний контакт» під кожну програму — синтетична
ground-truth (фото дає ПАРАМЕТРИ, не призначення контактів). Цінність демо —
sample-efficiency: скільки проб треба, щоб знайти конфіг, проти ручного перебору.
"""

from __future__ import annotations

import numpy as np

from .bopt import bayes_optimize, queries_to_target, random_search
from .stim_programs import PROGRAMS

N_CONTACTS = 16
_TARGET = 0.9          # selectivity fraction we count as "found"
_WIDTH = 0.06          # how localized the best contact's recruitment is


def _true_best(slot: str, label: str) -> int:
    """Deterministic ground-truth best contact for a program (stable across runs)."""
    h = sum(ord(c) for c in (slot + label))
    return h % N_CONTACTS


def _objective(best_idx: int):
    pos = np.linspace(0.0, 1.0, N_CONTACTS)
    best_pos = pos[best_idx]

    def obj(x: np.ndarray) -> float:
        d = float(x[0]) - best_pos
        return float(np.exp(-(d * d) / (2 * _WIDTH * _WIDTH)))
    return obj


def map_program(slot: str, label: str, seed: int = 0) -> dict:
    cands = np.linspace(0.0, 1.0, N_CONTACTS).reshape(-1, 1)
    best_idx = _true_best(slot, label)
    obj = _objective(best_idx)
    gp = bayes_optimize(obj, cands, n_init=3, n_iter=12, seed=seed)
    rnd = random_search(obj, cands, n_queries=gp["n_queries"], seed=seed)
    # bayes_optimize's best_index is a position in the query order, not a contact
    # index — map it back to the actual contact that scored best.
    queried = [int(c) for c in gp["queried"]]   # coerce numpy ints for JSON
    found_contact = queried[gp["best_index"]]
    return {
        "slot": slot, "label": label,
        "true_best": int(best_idx), "found_best": int(found_contact),
        "queried": queried,                  # order contacts were probed (for animation)
        "history": [round(v, 3) for v in gp["history"]],
        "rand_history": [round(v, 3) for v in rnd["history"]],
        "gp_queries": queries_to_target(gp["history"], _TARGET),
        "rand_queries": queries_to_target(rnd["history"], _TARGET),
        "hit": int(found_contact == best_idx),
    }


def map_all(seed: int = 0) -> dict:
    rows = [map_program(p.slot, p.label, seed=seed + i) for i, p in enumerate(PROGRAMS)]
    gp_mean = float(np.mean([r["gp_queries"] for r in rows]))
    rand_mean = float(np.mean([r["rand_queries"] for r in rows]))
    hit_rate = float(np.mean([r["hit"] for r in rows]))
    return {
        "n_contacts": N_CONTACTS,
        "programs": rows,
        "metrics": {
            "n_programs": len(rows),
            "gp_mean_queries": round(gp_mean, 1),
            "rand_mean_queries": round(rand_mean, 1),
            "speedup": round(rand_mean / max(1e-9, gp_mean), 1),
            "hit_rate": round(hit_rate, 2),
        },
    }
