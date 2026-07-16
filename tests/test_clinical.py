"""Clinical decision-support mapping tests — safety + convergence."""

from __future__ import annotations

import numpy as np

from bso.clinical_mapping import ClinicalMappingSession, StimConfig
from bso.config.limits import LIMITS


def test_suggestions_are_always_within_safety_limits():
    s = ClinicalMappingSession(n_contacts=16, target="test")
    rng = np.random.default_rng(0)
    for _ in range(15):
        cfg = s.suggest_next()
        assert cfg.within_limits()
        assert cfg.amplitude_mA <= LIMITS.amplitude_max_mA
        charge = cfg.amplitude_mA * cfg.pulse_width_us / 1000.0
        assert charge <= LIMITS.charge_per_phase_max_uC + 1e-9
        s.record(cfg, float(rng.random()))


def test_unsafe_config_flagged():
    bad = StimConfig(0, amplitude_mA=99.0, pulse_width_us=500.0)
    assert not bad.within_limits()


def test_session_converges_to_good_config():
    def resp(cfg, best_contact=7):
        charge = cfg.amplitude_mA * cfg.pulse_width_us / 250.0
        sel = np.exp(-((cfg.contact - best_contact) / 1.3) ** 2)
        act = 1.0 / (1.0 + np.exp(-1.5 * (charge - 3.0)))
        return float(np.clip(sel * act - max(0.0, charge - 6.0) * 0.15, 0, 1))

    s = ClinicalMappingSession(n_contacts=16)
    for _ in range(12):
        c = s.suggest_next()
        s.record(c, resp(c))
    # within 12 clinician trials it should find a contact near the true best (7)
    assert abs(s.best().config.contact - 7) <= 2
    assert s.best().response > 0.5


def test_report_contains_recommendation():
    s = ClinicalMappingSession()
    c = s.suggest_next()
    s.record(c, 0.7, note="ok")
    r = s.report()
    assert "Recommended program" in r
    assert "DECISION SUPPORT ONLY" in r
