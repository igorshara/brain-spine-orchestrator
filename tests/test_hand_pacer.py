"""Hand pacer — the patient's arm rhythm sets cadence through a bad leg decoder.

Locks in IZAR invention #3: when the leg-intent decoder is stuck/biased, the
manual (hand-paced) orchestrator tracks the patient's true intended cadence,
while the free-running orchestrator follows the wrong decoder. Default behaviour
(cadence_source="intent", no pacer) is unchanged.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scenarios.hand_pacer import _achieved_cadence, _run, TRUE_AFTER, TRUE_BEFORE, T_CHANGE, DUR


def test_hand_pacer_tracks_true_cadence_through_bad_decoder():
    free = _run(hand=False)
    hand = _run(hand=True)
    free_after = _achieved_cadence(free, T_CHANGE + 1.0, DUR - 0.5)
    hand_after = _achieved_cadence(hand, T_CHANGE + 1.0, DUR - 0.5)
    # hand pacer follows the patient up to ~84; free-running stays near the
    # decoder's wrong ~60.
    assert abs(hand_after - TRUE_AFTER) < abs(free_after - TRUE_AFTER)
    assert abs(hand_after - TRUE_AFTER) < 6.0
    assert abs(free_after - TRUE_AFTER) > 15.0


def test_both_match_before_the_change():
    """Before the speed-up both arms walk near the true 60 — the difference is
    purely the decoder failing to track the patient's change."""
    free = _run(hand=False)
    hand = _run(hand=True)
    for rec in (free, hand):
        c = _achieved_cadence(rec, 2.0, T_CHANGE - 0.5)
        assert abs(c - TRUE_BEFORE) < 6.0


def test_default_orchestrator_unchanged():
    """No hand_cadence -> cadence_source stays 'intent', default wiring intact."""
    from bso.runtime import build_system
    from bso.decoder_stub import IntentEvent
    from bso.schemas import Mode
    s = build_system([IntentEvent(0.0, Mode.STAND), IntentEvent(1.0, Mode.WALK, speed=0.5)])
    assert s.orchestrator.cadence_source == "intent"
