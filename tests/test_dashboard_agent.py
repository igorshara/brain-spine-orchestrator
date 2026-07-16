"""In-dashboard assistant: deterministic answers + proactive comments (EN default)."""

from __future__ import annotations

from bso.dashboard_agent import (
    answer,
    comment_on,
    comment_on_tab,
    data_context,
    session_summary,
)


def test_walking_question_lists_real_programs():
    a = answer("What are my walking programs?", use_llm=False)
    assert a["source"] == "rules"
    assert "A2" in a["text"] and "Hz" in a["text"]


def test_specific_slot_lookup():
    a = answer("what is A2?", use_llm=False)
    assert "Walking 1" in a["text"]


def test_highest_frequency_question():
    a = answer("which has the highest frequency?", use_llm=False)
    assert "90Hz" in a["text"] or "90 Hz" in a["text"]


def test_safety_question_mentions_guardian():
    a = answer("tell me about safety and dysreflexia", use_llm=False)
    assert "dysreflexia" in a["text"].lower()


def test_unknown_question_falls_back_without_llm():
    a = answer("what is the weather tomorrow", use_llm=False)
    assert a["source"] == "fallback"


def test_data_context_contains_real_programs():
    ctx = data_context()
    assert "A2" in ctx and "Walking" in ctx


def test_comment_on_state_names_program():
    c = comment_on({"intent": "walk", "intent_conf": 0.9})
    assert "Walking" in c["headline"]
    assert isinstance(c["advice"], list)


def test_session_summary_is_holistic_and_honest():
    s = session_summary()
    assert "20" in s
    assert "simulation" in s.lower()


def test_overview_via_question():
    a = answer("give me the big picture", use_llm=False)
    assert a["source"] == "rules"
    assert "picture" in a["text"].lower()


def test_tab_comment_per_tab():
    assert "OpenSim" in comment_on_tab("osim", {"muscles": 18, "lr_hip_corr": -0.7})
    assert "bladder" in comment_on_tab("auto", {"peak_pressure": 54, "residual_ml": 30,
                                                "ad_events": 0}).lower()


def test_ukrainian_available():
    a = answer("Які в мене програми ходьби?", use_llm=False, lang="ua")
    assert "ходьби" in a["text"].lower()
