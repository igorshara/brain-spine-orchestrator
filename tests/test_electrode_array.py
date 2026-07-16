"""Electrode paddle (Specify 5-6-5) + agent parameter planner."""

from __future__ import annotations

from bso.electrode_array import CONTACTS, contacts_for_goal, layout
from bso.stim_planner import learn_rules, recommend_parameters


def test_paddle_has_16_contacts_in_565():
    assert len(CONTACTS) == 16
    cols = layout()["columns"]
    assert (cols["L"], cols["M"], cols["R"]) == (5, 6, 5)


def test_every_contact_labeled():
    for c in CONTACTS:
        assert c.target and c.role and c.level


def test_autonomic_contact_targets_pelvic():
    blad = contacts_for_goal("bladder")
    assert blad and any("bladder" in c.target for c in blad)


def test_walking_engages_flexors_and_extensors():
    cs = contacts_for_goal("walking")
    roles = {c.role for c in cs}
    assert "extensor" in roles and ("flexor" in roles or "dorsiflexor" in roles)


def test_learned_rules_capture_walk_vs_stand_frequency():
    r = learn_rules()
    assert r["walking"]["rate_hz"][1] > r["standing"]["rate_hz"][1]  # walk higher Hz


def test_recommend_parameters_returns_contacts_and_params():
    rec = recommend_parameters("standing")
    assert rec["contacts"] and rec["params"]
    assert rec["tuning_plan"]["expected_probes"] < rec["tuning_plan"]["vs_grid_probes"]


def test_recommend_for_pelvic_goal_has_contact_even_without_program():
    rec = recommend_parameters("erectile")
    assert rec["contacts"]  # anatomy gives a contact even if no named program
