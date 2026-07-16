"""Layer 5 — Safety Supervisor. Absolute veto over every StimCommand.

Шар 5 — супервізор безпеки. Єдина точка, через яку проходить КОЖНА StimCommand.
Deterministic, no ML, fully test-covered. Veto authority is absolute: no agent
can bypass it. The supervisor may CLAMP a command into the safe envelope or
BLOCK it entirely, and it owns the emergency stop (e-stop).

Design rule (canon §1.3, §1.4): hard limits are constants in config/limits.py
and are never exceeded in simulation.
"""

from __future__ import annotations

import math
from dataclasses import replace

from .config.limits import LIMITS, SafetyLimits
from .schemas import SafetyVerdict, StimCommand


class SafetySupervisor:
    """Synchronous gate in the path of every StimCommand.

    State it maintains (all simulation proxies):
      * per-channel thermal accumulator (heating proxy),
      * per-channel autonomic-dysreflexia (AD) proxy over a sliding window,
      * per-channel last-seen timestamp for the liveness watchdog,
      * a latched e-stop flag.
    """

    def __init__(self, limits: SafetyLimits = LIMITS) -> None:
        self.limits = limits
        self._thermal: dict[str, float] = {}
        self._ad: dict[str, float] = {}
        self._last_seen: dict[str, float] = {}
        self._estopped = False
        self.blocked_count = 0
        self.clamped_count = 0
        self.approved_count = 0
        # Autonomic-dysreflexia watchdog (organ-distension path). The supervisor
        # owns the AD proxy for the autonomic loop too (canon §3, Layer 5).
        self.autonomic_ad_risk = 0.0
        self.autonomic_ad_events = 0

    def update_autonomic_dysreflexia(self, pressure_cmH2O: float, trigger_cmH2O: float) -> bool:
        """Life-safety: distension/pressure below the lesion can provoke AD — a
        dangerous BP surge. Tracks a normalized risk; returns True when the
        watchdog trips. Independent of the per-command stimulation path."""
        over = max(0.0, pressure_cmH2O - trigger_cmH2O)
        self.autonomic_ad_risk = min(1.0, over / 25.0)  # dangerous ~25 cmH2O over trigger
        if self.autonomic_ad_risk >= 1.0:
            self.autonomic_ad_events += 1
            return True
        return False

    # ------------------------------------------------------------------ e-stop
    def trigger_estop(self, reason: str = "manual e-stop") -> None:
        """Latch the emergency stop. Once latched, every command is blocked to
        zero output until :meth:`reset_estop` is called."""
        self._estopped = True
        self._estop_reason = reason

    def reset_estop(self) -> None:
        self._estopped = False

    @property
    def estopped(self) -> bool:
        return self._estopped

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _clamp(value: float, lo: float, hi: float) -> tuple[float, bool]:
        c = min(max(value, lo), hi)
        return c, (c != value)

    def _charge_density(self, charge_uC: float) -> float:
        return charge_uC / self.limits.electrode_area_cm2

    # -------------------------------------------------------------------- main
    def check(self, cmd: StimCommand) -> SafetyVerdict:
        """Validate (and if needed clamp/block) a single command. Pure w.r.t.
        the command; mutates only the supervisor's internal proxies."""
        L = self.limits
        ch = cmd.channel_id
        self._last_seen[ch] = cmd.t

        # 0) e-stop dominates everything: force output to zero.
        if self._estopped:
            self.blocked_count += 1
            safe = replace(cmd, amplitude_mA=0.0)
            return SafetyVerdict(
                approved=False,
                clamped=True,
                reason=f"e-stop latched: {getattr(self, '_estop_reason', 'unknown')}",
                command=safe,
            )

        # 1) Reject non-finite / negative-nonsense before any math.
        for name, v in (
            ("amplitude_mA", cmd.amplitude_mA),
            ("pulse_width_us", cmd.pulse_width_us),
            ("frequency_Hz", cmd.frequency_Hz),
        ):
            if not math.isfinite(v):
                self.blocked_count += 1
                return SafetyVerdict(
                    approved=False,
                    clamped=True,
                    reason=f"non-finite {name}={v!r}",
                    command=replace(cmd, amplitude_mA=0.0),
                )

        reasons: list[str] = []
        clamped = False

        # 2) Per-parameter clamps to the hard envelope.
        amp, c1 = self._clamp(cmd.amplitude_mA, L.amplitude_min_mA, L.amplitude_max_mA)
        pw, c2 = self._clamp(cmd.pulse_width_us, L.pulse_width_min_us, L.pulse_width_max_us)
        freq, c3 = self._clamp(cmd.frequency_Hz, L.frequency_min_Hz, L.frequency_max_Hz)
        if c1:
            reasons.append("amplitude clamped")
        if c2:
            reasons.append("pulse_width clamped")
        if c3:
            reasons.append("frequency clamped")
        clamped = clamped or c1 or c2 or c3

        safe = replace(cmd, amplitude_mA=amp, pulse_width_us=pw, frequency_Hz=freq)

        # 3) Charge per phase: Q = I * PW. If over cap, reduce amplitude to fit.
        if safe.charge_per_phase_uC > L.charge_per_phase_max_uC:
            new_amp = L.charge_per_phase_max_uC * 1000.0 / max(safe.pulse_width_us, 1e-9)
            new_amp = min(new_amp, L.amplitude_max_mA)
            safe = replace(safe, amplitude_mA=new_amp)
            reasons.append("charge/phase clamped")
            clamped = True

        # 4) Charge density per phase.
        if self._charge_density(safe.charge_per_phase_uC) > L.charge_density_max_uC_per_cm2:
            max_q = L.charge_density_max_uC_per_cm2 * L.electrode_area_cm2
            new_amp = max_q * 1000.0 / max(safe.pulse_width_us, 1e-9)
            safe = replace(safe, amplitude_mA=min(new_amp, safe.amplitude_mA))
            reasons.append("charge-density clamped")
            clamped = True

        # 5) Thermal proxy: integrate delivered power, decay handled in tick().
        #    power ~ amplitude^2 * pulse_width * frequency.
        power = (safe.amplitude_mA ** 2) * safe.pulse_width_us * safe.frequency_Hz
        therm = self._thermal.get(ch, 0.0) + L.thermal_gain * power
        if therm > L.thermal_proxy_max:
            # Block this command (force off) to let the channel cool.
            self._thermal[ch] = therm  # record the overshoot for cooling
            self.blocked_count += 1
            return SafetyVerdict(
                approved=False,
                clamped=True,
                reason="; ".join([*reasons, "thermal proxy over limit -> blocked"]),
                command=replace(safe, amplitude_mA=0.0),
            )
        self._thermal[ch] = therm

        # 6) AD (autonomic dysreflexia) proxy: sustained high charge.
        if safe.charge_per_phase_uC >= L.ad_proxy_charge_threshold_uC:
            self._ad[ch] = min(L.ad_proxy_max, self._ad.get(ch, 0.0) + 0.1)
        else:
            self._ad[ch] = max(0.0, self._ad.get(ch, 0.0) - 0.05)
        if self._ad[ch] >= L.ad_proxy_max:
            self.blocked_count += 1
            return SafetyVerdict(
                approved=False,
                clamped=True,
                reason="; ".join([*reasons, "AD watchdog proxy tripped -> blocked"]),
                command=replace(safe, amplitude_mA=0.0),
            )

        if clamped:
            self.clamped_count += 1
        else:
            self.approved_count += 1
        return SafetyVerdict(
            approved=True,
            clamped=clamped,
            reason="; ".join(reasons) if reasons else "ok",
            command=safe,
        )

    # ------------------------------------------------------------- maintenance
    def tick(self, t: float, dt: float) -> list[str]:
        """Per-timestep maintenance: cool the thermal proxy and enforce the
        liveness watchdog. Returns channel ids zeroed by the watchdog this tick.

        Called by the runtime once per step (after commands are processed)."""
        L = self.limits
        decay = math.exp(-L.thermal_decay_per_s * dt)
        for ch in list(self._thermal.keys()):
            self._thermal[ch] *= decay

        zeroed: list[str] = []
        for ch, last in list(self._last_seen.items()):
            if t - last > L.command_timeout_s:
                zeroed.append(ch)
        return zeroed

    # ------------------------------------------------------------- introspection
    def thermal(self, channel_id: str) -> float:
        return self._thermal.get(channel_id, 0.0)

    def ad_proxy(self, channel_id: str) -> float:
        return self._ad.get(channel_id, 0.0)
