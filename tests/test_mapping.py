"""Automatic electrode-mapping tests."""

from __future__ import annotations

import numpy as np

from bso.mapping import (
    GROUPS,
    ElectrodeArray,
    auto_map,
    best_contact_per_group,
    mapping_accuracy,
    selectivity,
)


def test_auto_mapping_beats_naive_default():
    arr = ElectrodeArray()
    W_hat, _, trials = auto_map(arr)
    acc = mapping_accuracy(W_hat, arr.W)
    truth = best_contact_per_group(arr.W)
    naive = {g: i for i, g in enumerate(GROUPS)}
    naive_acc = sum(naive[g] == truth[g] for g in GROUPS) / len(GROUPS)
    assert acc > 0.6, f"auto-mapping accuracy too low: {acc:.2f}"
    assert acc > naive_acc * 2, "auto-mapping should far exceed a naive default"
    assert trials <= 16 * 8, "probe budget bounded"


def test_recovered_map_correlates_with_truth():
    arr = ElectrodeArray()
    W_hat, _, _ = auto_map(arr)
    r = np.corrcoef(arr.W.ravel(), W_hat.ravel())[0, 1]
    assert r > 0.7, f"recovered map weakly correlated: r={r:.2f}"


def test_selectivity_of_selected_contacts_is_reasonable():
    arr = ElectrodeArray()
    W_hat, _, _ = auto_map(arr)
    est = best_contact_per_group(W_hat)
    sel = np.mean([selectivity(arr.W, est[g], gi) for gi, g in enumerate(GROUPS)])
    assert sel > 0.4


def test_stimulate_is_side_specific():
    arr = ElectrodeArray()
    # A left contact should drive left groups more than right groups at high amp.
    resp = arr.stimulate(1, 8.0)
    left = sum(resp[i] for i, g in enumerate(GROUPS) if g.startswith("L"))
    right = sum(resp[i] for i, g in enumerate(GROUPS) if g.startswith("R"))
    assert left > right
