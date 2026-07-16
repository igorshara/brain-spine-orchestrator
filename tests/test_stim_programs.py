"""Tests for Igor's real Medtronic program map."""

from __future__ import annotations

from bso.stim_programs import PROGRAMS, for_intent, recommend, summary


def test_all_programs_parsed():
    s = summary()
    assert s["n_programs"] == 20
    assert s["groups"] == ["A", "B", "C"]


def test_ranges_are_ordered_and_sane():
    for p in PROGRAMS:
        assert p.pw_us[0] <= p.pw_us[1]
        assert 100 <= p.pw_us[0] <= 1000      # pulse width µs
        assert p.rate_hz[0] <= p.rate_hz[1]
        assert 1 <= p.rate_hz[0] <= 200        # frequency Hz
        assert p.amp[0] <= p.amp[1]


def test_walking_programs_exist_and_are_high_rate():
    walk = for_intent("walk")
    assert walk, "expected walking programs"
    best = recommend("walk")
    # the canonical stepping pick should be a genuinely high-frequency config
    assert best.rate_hz[1] >= 85


def test_standing_is_low_frequency_vs_walking():
    stand = [p for p in PROGRAMS if p.goal == "standing"]
    walk_hi = recommend("walk")
    assert all(p.rate_hz[1] <= 20 for p in stand)   # tonic / postural = low Hz
    assert walk_hi.rate_hz[1] > 20                   # stepping = higher Hz


def test_recommend_covers_each_decoded_intent():
    for it in ("idle", "stand", "walk"):
        assert recommend(it) is not None


def test_mid_returns_center_of_range():
    p = recommend("walk")
    m = p.mid()
    assert p.pw_us[0] <= m["pw_us"] <= p.pw_us[1]
