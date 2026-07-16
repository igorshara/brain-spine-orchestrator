"""Autonomic neuromodulation tests — bladder, bowel, erectile + AD safety.

Перевіряють клінічно осмислений контраст: координована нейромодуляція дає
спорожнення при НИЖЧОМУ тиску, ПОВНІШЕ спорожнення і ВІДВЕРТАЄ автономну
дисрефлексію (загроза життю) порівняно з патологічним рефлексом (дисинергія).
"""

from __future__ import annotations

import numpy as np

from bso.autonomic import (
    AD_PRESSURE_TRIGGER_cmH2O,
    AutonomicCommand,
    AutonomicEvent,
    AutonomicFunction,
    AutonomicOrchestrator,
    BowelModel,
    ErectileModel,
    build_autonomic_system,
    build_managed_bladder_system,
    simulate_bladder,
)
from bso.config.limits import LIMITS
from bso.safety import SafetySupervisor


def _void_metrics(modulation):
    bl, ad, rec = simulate_bladder(modulation=modulation)
    peak = np.array(rec.bladder_pressure[1200:]).max()
    residual = rec.bladder_volume[-1]
    return peak, residual, len(ad.events), ad.systolic_rise


def test_coordination_lowers_void_pressure():
    dsd_peak, *_ = _void_metrics(False)
    syn_peak, *_ = _void_metrics(True)
    assert syn_peak < dsd_peak, "coordinated void should be lower pressure than DSD"


def test_coordination_improves_emptying():
    _, dsd_residual, _, _ = _void_metrics(False)
    _, syn_residual, _, _ = _void_metrics(True)
    assert syn_residual < dsd_residual * 0.5, "coordination should empty far more completely"


def test_coordination_prevents_autonomic_dysreflexia():
    _, _, dsd_ad, dsd_bp = _void_metrics(False)
    _, _, syn_ad, syn_bp = _void_metrics(True)
    assert dsd_ad > 0 and dsd_bp > 40, "DSD high pressure should trigger AD in the sim"
    assert syn_ad == 0 and syn_bp < 40, "coordination should prevent the AD surge"


def test_dyssynergia_produces_dangerous_pressure():
    peak, _, _, _ = _void_metrics(False)
    assert peak > AD_PRESSURE_TRIGGER_cmH2O, "dyssynergic void should reach the danger zone"


def test_bowel_coordination_improves_evacuation():
    def run(mod):
        b = BowelModel()
        orch = AutonomicOrchestrator(modulation=mod)
        for _ in range(600):
            b.dyssynergia = not mod
            b.step(orch.drive_for(AutonomicCommand.VOID), AutonomicCommand.VOID, 0.1)
        return b.content

    assert run(True) < run(False), "coordinated bowel should evacuate more completely"


def test_erectile_requires_stimulation():
    def run(mod):
        e = ErectileModel()
        orch = AutonomicOrchestrator(modulation=mod)
        for _ in range(200):
            e.step(orch.drive_for(AutonomicCommand.ENGAGE), AutonomicCommand.ENGAGE, 0.1)
        return e.functional

    assert run(True) and not run(False)


# --- integrated loop on the SHARED Bus / TickLoop / SafetySupervisor ---

def _bladder_schedule():
    return [AutonomicEvent(0.0, AutonomicFunction.BLADDER, AutonomicCommand.STORE),
            AutonomicEvent(120.0, AutonomicFunction.BLADDER, AutonomicCommand.VOID)]


def test_integrated_loop_routes_through_shared_safety():
    safety = SafetySupervisor()
    sys_ = build_autonomic_system(_bladder_schedule(), modulation=True, safety=safety)
    sys_.run(180.0)
    # Autonomic stimulation actually passed through the same supervisor.
    assert safety.approved_count > 0


def test_integrated_loop_reproduces_contrast():
    def metrics(mod):
        sys_ = build_autonomic_system(_bladder_schedule(), modulation=mod)
        log = sys_.run(180.0)
        void = [s for s in log if s and s["function"] == "bladder"]
        peak = max(s["pressure"] for s in void[1200:])
        return peak, void[-1]["volume"]

    dsd_peak, dsd_res = metrics(False)
    syn_peak, syn_res = metrics(True)
    assert syn_peak < dsd_peak and syn_res < dsd_res * 0.5


def test_shared_supervisor_ad_watchdog_trips_for_dsd_only():
    def ad_events(mod):
        s = SafetySupervisor()
        build_autonomic_system(_bladder_schedule(), modulation=mod, safety=s).run(180.0)
        return s.autonomic_ad_events

    assert ad_events(False) > 0
    assert ad_events(True) == 0


def test_managed_bladder_voids_and_prevents_ad():
    safety = SafetySupervisor()
    sysm = build_managed_bladder_system(modulation=True, safety=safety)
    log = [x for x in sysm.run(600.0) if x and x["function"] == "bladder"]
    # The controller voids multiple times, keeps pressure safe, and prevents AD.
    assert sysm.manager.void_count >= 1
    assert max(x["pressure"] for x in log) < 60
    assert max(x["volume"] for x in log) <= 260  # bounded below the danger reflex
    assert safety.autonomic_ad_events == 0


def test_managed_bladder_beats_unmanaged_on_ad():
    s_un = SafetySupervisor()
    build_autonomic_system(
        [AutonomicEvent(0.0, AutonomicFunction.BLADDER, AutonomicCommand.STORE)],
        modulation=False, dyssynergia=True, safety=s_un).run(600.0)
    s_man = SafetySupervisor()
    build_managed_bladder_system(modulation=True, safety=s_man).run(600.0)
    assert s_un.autonomic_ad_events > 100  # unmanaged dyssynergia provokes AD repeatedly
    assert s_man.autonomic_ad_events == 0


def test_timed_voiding_protocol_triggers_voids():
    safety = SafetySupervisor()
    sysm = build_managed_bladder_system(modulation=True, safety=safety, schedule_interval_s=150)
    sysm.run(600.0)
    assert sysm.manager.void_count >= 2


def test_shared_supervisor_clamps_over_limit_autonomic_command():
    from bso.schemas import StimCommand
    safety = SafetySupervisor()
    over = StimCommand(t=0.0, channel_id="ch_auto_detrusor", amplitude_mA=999.0,
                       pulse_width_us=200.0, frequency_Hz=30.0)
    verdict = safety.check(over)
    assert verdict.command.amplitude_mA <= LIMITS.amplitude_max_mA + 1e-9
