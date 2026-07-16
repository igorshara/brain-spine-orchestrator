"""Predictive autonomic-dysreflexia (AD) guardian — an always-on safety idea.

Унікальна ідея «автономіка-перша»: автономна дисрефлексія (АД) — раптовий, смертельно
небезпечний стрибок тиску від розтягнення нижче рівня травми (найчастіше — міхур).
У клініці її лікують РЕАКТИВНО (коли вже сталась). Тут — ПРЕДИКТИВНИЙ вартовий, що
працює 24/7 на дешевих носимих: за трендом тиску/наповнення він ПРОГНОЗУЄ напад
заздалегідь і запобігає йому (вчасне координоване спорожнення + попередження з часом
випередження), ДО входу в небезпечну зону.

Це те, чого по суті ніхто не робить (АД — реактивна в клініці). Працює на нашій
моделі міхура. Усе ILLUSTRATIVE — дослідницька симуляція, не медичний пристрій.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .autonomic import (
    AD_PRESSURE_TRIGGER_cmH2O,
    AutonomicCommand,
    AutonomicDysreflexiaMonitor,
    BladderModel,
    StimDrive,
)


@dataclass
class ADGuardian:
    """Forecasts organ pressure ahead from its recent trend and warns/acts before
    AD. The lead time is how early it flags danger versus when AD would occur."""

    horizon_s: float = 40.0          # how far ahead it forecasts
    warn_pressure_cmH2O: float = 22.0  # act if forecast crosses this (well below AD trigger)
    _hist: deque = field(default_factory=lambda: deque(maxlen=12))

    def observe(self, t: float, pressure: float) -> dict:
        self._hist.append((t, pressure))
        slope = 0.0
        if len(self._hist) >= 3:
            (t0, p0), (t1, p1) = self._hist[0], self._hist[-1]
            slope = (p1 - p0) / (t1 - t0) if t1 > t0 else 0.0
        forecast = pressure + slope * self.horizon_s
        warn = forecast >= self.warn_pressure_cmH2O
        # lead time to the AD trigger at the current rate (info for the patient)
        lead = ((AD_PRESSURE_TRIGGER_cmH2O - pressure) / slope) if slope > 1e-6 else float("inf")
        return {"warn": warn, "forecast": forecast, "slope": slope, "lead_to_AD_s": lead}


def simulate(policy: str, fill_ml_per_s: float = 1.5, dur_s: float = 600.0, dt: float = 0.5):
    """policy in {'none','reactive','predictive'}. Returns time series + metrics.
    'reactive' voids only once pressure is already near the danger zone; 'predictive'
    uses the guardian's forecast to void early."""
    bladder = BladderModel(dyssynergia=True, inflow_ml_per_s=fill_ml_per_s)
    bladder.pressure_cmH2O = bladder.volume_ml / bladder.compliance  # init (avoid 0->jump slope)
    ad = AutonomicDysreflexiaMonitor()
    guard = ADGuardian()
    coord = StimDrive(organ_drive=0.35, sphincter_relax=0.92)  # coordinated (safe) void
    voiding = False
    first_warn_t = None
    rec = {"t": [], "volume": [], "pressure": [], "bp": [], "warn": []}
    t = 0.0
    n = int(dur_s / dt)
    for _ in range(n):
        info = guard.observe(t, bladder.pressure_cmH2O)
        # decide command
        if policy == "predictive":
            if info["warn"]:
                voiding = True
                if first_warn_t is None:
                    first_warn_t = t
            if voiding and bladder.volume_ml <= 25:
                voiding = False
        elif policy == "reactive":
            # act only once pressure is already high (near danger) — too late in DSD
            if bladder.pressure_cmH2O >= 50.0:
                voiding = True
            if voiding and bladder.volume_ml <= 25:
                voiding = False
        cmd = AutonomicCommand.VOID if voiding else AutonomicCommand.STORE
        # coordinated drive only when the guardian/system commands a void
        bladder.dyssynergia = not (voiding and policy in ("predictive", "reactive"))
        drive = coord if (voiding and policy != "none") else StimDrive()
        bladder.step(drive, cmd, dt)
        bp = ad.update(t, bladder.pressure_cmH2O, dt)
        rec["t"].append(t)
        rec["volume"].append(bladder.volume_ml)
        rec["pressure"].append(bladder.pressure_cmH2O)
        rec["bp"].append(bp)
        rec["warn"].append(1 if (policy == "predictive" and info["warn"]) else 0)
        t += dt
    metrics = {
        "policy": policy,
        "ad_events": len(ad.events),
        "peak_bp_rise": round(max(b - ad.baseline_bp for b in rec["bp"]), 1),
        "peak_pressure": round(max(rec["pressure"]), 1),
        "first_warning_s": round(first_warn_t, 1) if first_warn_t is not None else None,
        "first_ad_event_s": round(ad.events[0][0], 1) if ad.events else None,
    }
    return rec, metrics
