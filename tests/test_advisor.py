"""Live clinical advisor tests (English default, Ukrainian via lang)."""

from __future__ import annotations

from bso.advisor import P0, P1, assess


def test_ad_surge_is_p0_and_first():
    adv = assess({"ad_bp_rise": 30.0, "intent": "walk", "intent_conf": 0.9})
    assert adv[0].priority == P0
    assert "dysreflexia" in adv[0].title.lower()


def test_high_bladder_pressure_flags_p0():
    adv = assess({"bladder_pressure": 55.0})
    assert any(a.priority == P0 and "detrusor" in a.title.lower() for a in adv)


def test_weak_signal_warns():
    adv = assess({"sparing": 0.3, "intent": "walk", "intent_conf": 0.9})
    assert any(a.priority == P1 and "weak" in a.title.lower() for a in adv)


def test_confident_walk_enables_locomotion():
    adv = assess({"intent": "walk", "intent_conf": 0.92, "sparing": 0.8})
    assert any("locomotion" in a.title.lower() for a in adv)


def test_ambiguous_intent_blocks_locomotion():
    adv = assess({"intent": "walk", "intent_conf": 0.5, "sparing": 0.8})
    assert any(a.priority == P1 and "ambiguous" in a.title.lower() for a in adv)


def test_calm_state_is_ok():
    adv = assess({"intent": "stand", "intent_conf": 0.9, "sparing": 0.8,
                  "bladder_pressure": 20.0, "ad_bp_rise": 0.0})
    assert all(a.priority != P0 for a in adv)


def test_priority_ordering():
    adv = assess({"ad_bp_rise": 30.0, "sparing": 0.3, "intent": "stand", "intent_conf": 0.9})
    prios = [a.priority for a in adv]
    assert prios == sorted(prios)  # P0 before P1 before P2


def test_ukrainian_still_available():
    adv = assess({"bladder_pressure": 55.0}, lang="ua")
    assert any("детрузор" in a.title.lower() for a in adv)
