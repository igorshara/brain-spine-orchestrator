"""Exhaustive safety tests (canon M1). These are CRITICAL and must stay green.

Жоден тест безпеки не можна послаблювати заради проходження інших.
Invariant under test: no out-of-envelope command can ever be applied, clamps
are correct, and the e-stop zeroes all output.
"""

from __future__ import annotations

import math

import pytest

from bso.config.limits import LIMITS
from bso.safety import SafetySupervisor
from bso.schemas import StimCommand


def cmd(amp=2.0, pw=200.0, freq=40.0, ch="ch_test", t=0.0):
    return StimCommand(
        t=t, channel_id=ch, amplitude_mA=amp, pulse_width_us=pw, frequency_Hz=freq
    )


def test_in_envelope_command_approved_unclamped():
    s = SafetySupervisor()
    v = s.check(cmd(amp=1.0, pw=150.0, freq=40.0))
    assert v.approved
    assert not v.clamped
    assert v.command.amplitude_mA == 1.0


def test_amplitude_over_limit_is_clamped_not_exceeded():
    s = SafetySupervisor()
    v = s.check(cmd(amp=999.0, pw=100.0, freq=20.0))
    assert v.command.amplitude_mA <= LIMITS.amplitude_max_mA
    assert v.clamped


def test_negative_amplitude_clamped_to_min():
    s = SafetySupervisor()
    v = s.check(cmd(amp=-5.0))
    assert v.command.amplitude_mA >= LIMITS.amplitude_min_mA


def test_pulse_width_and_frequency_clamped():
    s = SafetySupervisor()
    v = s.check(cmd(amp=1.0, pw=99999.0, freq=99999.0))
    assert v.command.pulse_width_us <= LIMITS.pulse_width_max_us
    assert v.command.frequency_Hz <= LIMITS.frequency_max_Hz


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_is_blocked_and_zeroed(bad):
    s = SafetySupervisor()
    v = s.check(cmd(amp=bad))
    assert not v.approved
    assert v.command.amplitude_mA == 0.0


def test_charge_per_phase_never_exceeds_cap():
    s = SafetySupervisor()
    # Try to push huge charge: max amp * max pw.
    v = s.check(cmd(amp=LIMITS.amplitude_max_mA, pw=LIMITS.pulse_width_max_us, freq=10.0))
    assert v.command.charge_per_phase_uC <= LIMITS.charge_per_phase_max_uC + 1e-9


def test_charge_density_never_exceeds_cap():
    s = SafetySupervisor()
    v = s.check(cmd(amp=LIMITS.amplitude_max_mA, pw=LIMITS.pulse_width_max_us, freq=10.0))
    density = v.command.charge_per_phase_uC / LIMITS.electrode_area_cm2
    assert density <= LIMITS.charge_density_max_uC_per_cm2 + 1e-9


def test_estop_blocks_everything_and_zeroes_output():
    s = SafetySupervisor()
    s.trigger_estop("test")
    v = s.check(cmd(amp=1.0, pw=100.0, freq=20.0))
    assert not v.approved
    assert v.command.amplitude_mA == 0.0
    assert "e-stop" in v.reason


def test_estop_reset_restores_normal_operation():
    s = SafetySupervisor()
    s.trigger_estop()
    s.reset_estop()
    v = s.check(cmd(amp=1.0, pw=100.0, freq=20.0))
    assert v.approved


def test_thermal_proxy_blocks_after_sustained_high_power():
    s = SafetySupervisor()
    blocked = False
    # Hammer one channel at max power without letting it cool.
    for i in range(100000):
        v = s.check(cmd(amp=LIMITS.amplitude_max_mA, pw=300.0, freq=120.0, t=i * 0.001))
        if not v.approved and "thermal" in v.reason:
            blocked = True
            break
    assert blocked, "thermal proxy never tripped under sustained max power"


def test_thermal_proxy_cools_over_time():
    s = SafetySupervisor()
    ch = "ch_cool"
    for i in range(50):
        s.check(cmd(amp=8.0, pw=300.0, freq=120.0, ch=ch, t=i * 0.001))
    hot = s.thermal(ch)
    for _ in range(2000):
        s.tick(t=999.0, dt=0.005)
    assert s.thermal(ch) < hot


def test_watchdog_flags_stale_channels():
    s = SafetySupervisor()
    s.check(cmd(ch="ch_a", t=0.0))
    zeroed = s.tick(t=1.0, dt=0.005)  # far beyond command_timeout_s
    assert "ch_a" in zeroed


def test_counters_track_outcomes():
    s = SafetySupervisor()
    s.check(cmd(amp=1.0))  # approved
    s.check(cmd(amp=999.0))  # clamped
    s.trigger_estop()
    s.check(cmd(amp=1.0))  # blocked
    assert s.approved_count >= 1
    assert s.clamped_count >= 1
    assert s.blocked_count >= 1


def test_no_command_can_bypass_supervisor_envelope():
    """Fuzz: random-ish commands all come out within the hard envelope."""
    s = SafetySupervisor()
    vals = [-100.0, 0.0, 0.5, 3.3, 10.0, 50.0, 1e6]
    for a in vals:
        for pw in [-10.0, 0.0, 120.0, 500.0, 5000.0]:
            for f in [-1.0, 0.0, 40.0, 120.0, 1000.0]:
                v = s.check(cmd(amp=a, pw=pw, freq=f, t=0.0))
                c = v.command
                assert LIMITS.amplitude_min_mA <= c.amplitude_mA <= LIMITS.amplitude_max_mA
                assert LIMITS.pulse_width_min_us <= c.pulse_width_us <= LIMITS.pulse_width_max_us
                assert LIMITS.frequency_min_Hz <= c.frequency_Hz <= LIMITS.frequency_max_Hz
                assert c.charge_per_phase_uC <= LIMITS.charge_per_phase_max_uC + 1e-9
