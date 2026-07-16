"""Auto-mapping (GP-BO) on Igor's real programs."""

from __future__ import annotations

from bso.program_mapping import N_CONTACTS, map_all, map_program
from bso.stim_programs import PROGRAMS


def test_map_program_returns_probe_order():
    r = map_program("A2", "Walking 1", seed=0)
    assert 0 <= r["true_best"] < N_CONTACTS
    assert len(r["queried"]) == len(set(r["queried"]))   # no contact probed twice
    assert all(0 <= c < N_CONTACTS for c in r["queried"])


def test_history_is_monotone_nondecreasing():
    r = map_program("B2", "Walking 2", seed=1)
    h = r["history"]
    assert all(h[i] <= h[i + 1] + 1e-9 for i in range(len(h) - 1))


def test_map_all_covers_every_program():
    d = map_all(seed=0)
    assert d["metrics"]["n_programs"] == len(PROGRAMS)
    assert len(d["programs"]) == len(PROGRAMS)


def test_gp_bo_more_sample_efficient_than_random():
    d = map_all(seed=0)
    m = d["metrics"]
    # the clinical value we claim: GP-BO finds the contact in fewer probes
    assert m["gp_mean_queries"] <= m["rand_mean_queries"]
    assert m["speedup"] >= 1.0


def test_comment_uses_real_metrics():
    from bso.dashboard_agent import comment_on_tab
    txt = comment_on_tab("progmap", {"n_programs": 20, "gp_mean_queries": 5.0,
                                     "rand_mean_queries": 9.0, "speedup": 1.8})
    assert "20" in txt and "GP-BO" in txt
