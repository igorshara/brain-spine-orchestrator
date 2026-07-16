"""Recovery program management — SSoT + tracker + agent-fleet accelerator.

Система управління програмою відновлення Ігоря. Це ПРИСКОРЮВАЧ реального клінічного
шляху (не керує жодним приладом): єдине джерело правди (SQLite) про метрики функцій,
реабілітаційні сесії, рекомендовані стим-програми (з clinical_mapping), дослідницькі
ліди/випробування, партнерів і задачі — плюс щотижневий дайджест.

Детермінований кістяк працює БЕЗ API-ключа. LLM-наратив підключається автоматично,
коли у середовищі є ANTHROPIC_API_KEY (патерн інших проєктів Ігоря). Жодної дії над
реальним стимулятором — лише облік, координація й decision-support.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass

DOMAINS = ("movement", "bladder", "bowel", "erectile")  # 0..10 self/clinician score

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics(
  id INTEGER PRIMARY KEY, date TEXT, domain TEXT, score REAL, note TEXT);
CREATE TABLE IF NOT EXISTS sessions(
  id INTEGER PRIMARY KEY, date TEXT, kind TEXT, minutes INTEGER, program_id INTEGER, notes TEXT);
CREATE TABLE IF NOT EXISTS programs(
  id INTEGER PRIMARY KEY, date TEXT, target TEXT, contact INTEGER,
  amplitude_mA REAL, pulse_width_us REAL, frequency_Hz REAL, response REAL, note TEXT);
CREATE TABLE IF NOT EXISTS leads(
  id INTEGER PRIMARY KEY, title TEXT, source TEXT, url TEXT, relevance TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS partners(
  id INTEGER PRIMARY KEY, name TEXT, org TEXT, status TEXT, next_step TEXT);
CREATE TABLE IF NOT EXISTS tasks(
  id INTEGER PRIMARY KEY, description TEXT, owner TEXT, due TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS approvals(
  id INTEGER PRIMARY KEY, ts TEXT, kind TEXT, target TEXT, summary TEXT,
  decision TEXT, note TEXT, decided_by TEXT);
"""


@dataclass
class RecoveryDB:
    """SQLite single-source-of-truth for the recovery program."""

    path: str = ":memory:"

    def __post_init__(self) -> None:
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def _ins(self, table: str, **cols) -> int:
        keys = ",".join(cols)
        qs = ",".join("?" * len(cols))
        cur = self.conn.execute(f"INSERT INTO {table}({keys}) VALUES({qs})", tuple(cols.values()))
        self.conn.commit()
        return cur.lastrowid

    # --- writers ---
    def log_metric(self, date, domain, score, note=""):
        assert domain in DOMAINS, f"domain must be one of {DOMAINS}"
        return self._ins("metrics", date=date, domain=domain, score=float(score), note=note)

    def log_session(self, date, kind, minutes, program_id=None, notes=""):
        return self._ins("sessions", date=date, kind=kind, minutes=int(minutes),
                         program_id=program_id, notes=notes)

    def save_program(self, date, target, contact, amplitude_mA, pulse_width_us,
                     frequency_Hz, response, note=""):
        return self._ins("programs", date=date, target=target, contact=int(contact),
                         amplitude_mA=amplitude_mA, pulse_width_us=pulse_width_us,
                         frequency_Hz=frequency_Hz, response=response, note=note)

    def add_lead(self, title, source, url="", relevance="", status="new"):
        return self._ins("leads", title=title, source=source, url=url,
                         relevance=relevance, status=status)

    def add_partner(self, name, org, status="contacted", next_step=""):
        return self._ins("partners", name=name, org=org, status=status, next_step=next_step)

    def add_task(self, description, owner="Ihor", due="", status="open"):
        return self._ins("tasks", description=description, owner=owner, due=due, status=status)

    # --- readers ---
    def rows(self, table, where="", params=()):
        q = f"SELECT * FROM {table}" + (f" WHERE {where}" if where else "")
        return [dict(r) for r in self.conn.execute(q, params)]

    def progress(self, domain: str) -> dict:
        """Trend of a function domain: compares earlier vs recent mean score."""
        ms = sorted(self.rows("metrics", "domain=?", (domain,)), key=lambda r: r["date"])
        if len(ms) < 2:
            return {"domain": domain, "trend": "insufficient data", "latest": None}
        scores = [m["score"] for m in ms]
        half = max(1, len(scores) // 2)
        early, recent = sum(scores[:half]) / half, sum(scores[half:]) / (len(scores) - half)
        delta = recent - early
        trend = "improving" if delta > 0.3 else ("declining" if delta < -0.3 else "stable")
        return {"domain": domain, "trend": trend, "delta": round(delta, 2),
                "latest": scores[-1], "n": len(scores)}


def llm_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _llm_narrative(prompt: str) -> str | None:
    if not llm_available():
        return None
    try:
        import anthropic
        c = anthropic.Anthropic()
        m = c.messages.create(model="claude-opus-4-8", max_tokens=400,
                              messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in m.content if getattr(b, "type", "") == "text")
    except Exception:
        return None


def weekly_digest(db: RecoveryDB) -> str:
    """Deterministic recovery brief (LLM narrative added if a key is present)."""
    lines = ["# Тижневий зріз програми відновлення", ""]
    lines.append("## Функції (тренд)")
    for d in DOMAINS:
        p = db.progress(d)
        if p["latest"] is None:
            lines.append(f"- **{d}**: даних замало")
        else:
            arrow = {"improving": "↑", "declining": "↓", "stable": "→"}.get(p["trend"], "")
            lines.append(f"- **{d}**: {p['latest']:.1f}/10 {arrow} "
                         f"({p['trend']}, Δ{p.get('delta', 0):+.1f})")
    sess = db.rows("sessions")
    lines += ["", f"## Реабілітація\n- сесій у журналі: **{len(sess)}**, "
              f"сумарно {sum(s['minutes'] for s in sess)} хв"]
    progs = db.rows("programs")
    if progs:
        b = max(progs, key=lambda p: p["response"] or 0)
        lines.append(f"- найкраща стим-програма (decision-support): контакт {b['contact']}, "
                     f"{b['amplitude_mA']:.0f} мА, {b['pulse_width_us']:.0f} мкс "
                     f"(відгук {b['response']:.2f}) — для {b['target']}")
    leads = [r for r in db.rows("leads") if r["status"] != "closed"]
    lines += ["", "## Дослідження/випробування (scout)"]
    lines += [f"- {r['title']} [{r['source']}] — {r['relevance']} ({r['status']})" for r in leads] \
        or ["- немає активних лідів"]
    partners = db.rows("partners")
    lines += ["", "## Партнери"]
    lines += [f"- {p['name']} / {p['org']} — {p['status']}; далі: {p['next_step']}"
              for p in partners] or ["- немає"]
    tasks = [t for t in db.rows("tasks") if t["status"] == "open"]
    lines += ["", "## Відкриті задачі"]
    lines += [f"- [ ] {t['description']} ({t['owner']}, до {t['due']})"
              for t in tasks] or ["- немає"]

    narrative = _llm_narrative("Стисни цей зріз відновлення у 2-3 речення підтримки й "
                               "пріоритетів:\n" + "\n".join(lines))
    if narrative:
        lines += ["", "## Висновок (AI)", narrative]
    else:
        lines += ["", "_(LLM-наратив підключиться при ANTHROPIC_API_KEY у .env)_"]
    return "\n".join(lines)
