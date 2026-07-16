"""Residual-signal intent decoder tests (idea 4: no brain chip)."""

from __future__ import annotations

from bso.intent import INTENTS, IntentDecoder, ResidualSignalModel, decode_stream


def _trained(sparing=0.7):
    m = ResidualSignalModel(sparing=sparing, seed=1)
    X, y = m.dataset(200)
    return IntentDecoder(smooth=5).fit(X, y), X, y


def test_decoder_is_accurate_with_good_sparing():
    dec, X, y = _trained(0.8)
    assert dec.accuracy(X, y) > 0.85


def test_degrades_gracefully_with_sparing():
    hi = _trained(0.8)[0].accuracy(*ResidualSignalModel(0.8, seed=5).dataset(120))
    lo = _trained(0.3)[0].accuracy(*ResidualSignalModel(0.3, seed=5).dataset(120))
    assert hi >= lo  # more preserved signal -> at least as accurate


def test_smoothing_recovers_intent_stream():
    dec, _, _ = _trained(0.6)
    tl = [("idle", 15), ("stand", 15), ("walk", 30), ("idle", 15)]
    true, d, lat = decode_stream(dec, ResidualSignalModel(0.6, seed=2), tl)
    assert (true == d).mean() > 0.75   # decoded stream tracks the true intent
    assert lat < 8                     # locks on quickly after a change


def test_intent_classes_present():
    assert INTENTS == ["idle", "stand", "walk"]
