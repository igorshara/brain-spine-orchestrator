"""Safety hard-limits — constants only. NEVER exceeded in simulation.

УВАГА: усі значення нижче — ФІЗІОЛОГІЧНО ПРАВДОПОДІБНІ ПЛЕЙСХОЛДЕРИ.
They are ILLUSTRATIVE, not clinically validated, and must never be presented
as clinical settings. They exist so the safety supervisor has concrete numbers
to clamp against in the simulation.

Ranges are loosely inspired by the epidural electrical stimulation (EES)
literature but deliberately rounded; do not read clinical meaning into them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyLimits:
    # --- per-pulse electrical limits (ILLUSTRATIVE) ---
    # Envelope chosen to comfortably contain real clinical EES program ranges
    # (e.g. 12-16 mA, 550-600 us) with headroom, so the supervisor's "every command
    # is checked" invariant is consistent with real-device parameters. Still ILLUSTRATIVE.
    amplitude_min_mA: float = 0.0
    amplitude_max_mA: float = 20.0  # ILLUSTRATIVE (headroom over real 12-16 mA)
    pulse_width_min_us: float = 0.0
    pulse_width_max_us: float = 700.0  # ILLUSTRATIVE (headroom over real 550-600 us)
    frequency_min_Hz: float = 0.0
    frequency_max_Hz: float = 120.0  # ILLUSTRATIVE (real programs ~10-90 Hz)

    # --- charge limits (Shannon-style proxy), ILLUSTRATIVE ---
    # Charge per phase Q = I * PW. With 20 mA * 700 us = 14.0 uC absolute ceiling,
    # we keep a tighter operational cap below that. Real programs (~16 mA * 600 us
    # = 9.6 uC) pass within this envelope.
    charge_per_phase_max_uC: float = 12.0  # ILLUSTRATIVE
    # Charge density per phase = Q / electrode_area. Using a nominal contact area.
    electrode_area_cm2: float = 0.06  # ILLUSTRATIVE nominal contact area
    charge_density_max_uC_per_cm2: float = 220.0  # ILLUSTRATIVE (contains 12 uC / 0.06 cm2)

    # --- thermal / duty proxy (ILLUSTRATIVE) ---
    # A unitless accumulator proxy for tissue heating. Rises with delivered power
    # (~ amplitude^2 * pw * freq), decays each tick. Pure simulation construct.
    thermal_proxy_max: float = 1.0  # ILLUSTRATIVE ceiling (normalized)
    thermal_decay_per_s: float = 0.5  # how fast the proxy cools, 1/s
    # Calibrated (ILLUSTRATIVE) so normal operation stays well below the ceiling
    # while sustained near-maximum power trips the backstop. See safety.tick().
    thermal_gain: float = 2.0e-9  # scales raw power (amp^2*pw*freq) into the proxy

    # --- watchdog / autonomic-dysreflexia proxy (ILLUSTRATIVE) ---
    # Sustained high-charge stimulation is flagged. This is a SIM proxy only.
    ad_proxy_charge_threshold_uC: float = 3.0  # ILLUSTRATIVE
    ad_proxy_window_s: float = 2.0  # sustained-over-window trigger
    ad_proxy_max: float = 1.0  # normalized ceiling

    # --- command liveness watchdog ---
    # If no fresh command for a channel within this horizon, the channel is
    # zeroed (fail-safe to off).
    command_timeout_s: float = 0.25  # ILLUSTRATIVE


# Single shared instance used across the simulation.
LIMITS = SafetyLimits()
