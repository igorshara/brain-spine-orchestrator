"""Scheduled autonomic training — the «discipline the reflex» protocols.

Ідея Ігоря, оформлена як R&D-протокол. Замість того, щоб пацієнт катетеризувався
кожні 4 години наосліп, стимулятор САМ за розкладом:
  • МІХУР — кожні ~4 год вмикає координовану крижову стимуляцію (S2–S4), провокує
    низькотискове спорожнення (як Brindley/SARS), і з тижнями ТРЕНУЄ рефлекс:
    ємність росте, залишковий об'єм падає, дисинергія слабшає.
  • КИШКІВНИК — щоденна програма дефекації у фіксований час (привчання ритму).
  • ЕРЕКЦІЯ — за запитом: крижова парасимпатична стимуляція для тумесценції.

ЧЕСНА НАУКА (для перемовин, без overclaim):
  • Викликане сечовипускання/дефекація/ерекція крижовою стимуляцією — ВСТАНОВЛЕНА
    терапія (Brindley sacral anterior root stimulator; the device partner InterStim — сакральна
    нейромодуляція; EES-дослідження міхура leading researchers/a partner platform).
  • «Тренування рефлексу і мозку до дисципліни за розкладом» — це R&D-ГІПОТЕЗА,
    оперта на activity-dependent plasticity; тут МОДЕЛЮЄТЬСЯ як тренд, не доведено.
  • Усе проходить через ТОЙ САМИЙ safety-вартовий (автономна дисрефлексія, поріг the upper-tract criterion).

Числа ILLUSTRATIVE. Не медичний пристрій.
"""

from __future__ import annotations

from dataclasses import dataclass

from .autonomic import (
    AD_BP_RISE_LIMIT,
    AD_PRESSURE_TRIGGER_cmH2O,
    AutonomicCommand,
    BladderModel,
    SAFE_VOID_PRESSURE_cmH2O,
    StimDrive,
)

# S2 sacral contact on the 5-6-5 paddle array (matches electrode_array contact 6)
SACRAL_CONTACT = 6


@dataclass
class TrainingProtocol:
    function: str          # bladder | bowel | erectile
    label: str
    interval_h: float      # how often the schedule fires (0 = on-demand)
    rate_hz: float         # sacral stimulation frequency
    pw_us: float
    amp: float
    contact: int = SACRAL_CONTACT

    def as_dict(self) -> dict:
        return {"function": self.function, "label": self.label,
                "interval_h": self.interval_h, "rate_hz": self.rate_hz,
                "pw_us": self.pw_us, "amp": self.amp, "contact": self.contact}


# Frequencies are ILLUSTRATIVE, chosen near published sacral-neuromodulation ranges.
PROTOCOLS = {
    "bladder": TrainingProtocol("bladder", "Bladder void — every 4 h", 4.0,
                                rate_hz=15.0, pw_us=210.0, amp=6.0),
    "bowel": TrainingProtocol("bowel", "Bowel program — daily", 24.0,
                              rate_hz=20.0, pw_us=240.0, amp=7.0),
    "erectile": TrainingProtocol("erectile", "Erectile — on demand", 0.0,
                                 rate_hz=12.0, pw_us=200.0, amp=5.0),
}


def simulate_bladder_day(interval_h: float = 4.0, hours: float = 24.0,
                         trained: float = 0.0) -> dict:
    """Run a day of SCHEDULED, coordinated bladder voids. EES restores detrusor–
    sphincter SYNERGY, so each scheduled window empties at LOW pressure. `trained`
    0..1 (weeks of the regimen) raises capacity and void efficiency. Returns the
    24-h volume/pressure timeline, void times and a stable AD systolic-rise proxy."""
    dt = 2.0  # 2-s steps over a full day
    bladder = BladderModel(dyssynergia=False)   # coordinated EES = synergy restored
    bladder.capacity_ml = 450.0 + 150.0 * trained
    bladder.compliance = 12.0 + 9.0 * trained   # wall accommodates better with training
    # realistic diuresis: fill to ~80% of capacity by the next scheduled void
    bladder.inflow_ml_per_s = 0.8 * bladder.capacity_ml / (max(2.0, interval_h) * 3600)
    bladder.volume_ml = 0.30 * bladder.capacity_ml
    # Untrained = reflex-heavy, poorly-relaxing sphincter (DSD): high void pressure,
    # poor emptying. Trained = coordinated: gentle detrusor, sphincter relaxes ->
    # low pressure, near-complete emptying.
    drive = StimDrive(organ_drive=0.50 - 0.30 * trained,
                      sphincter_relax=0.30 + 0.65 * trained)
    store = StimDrive(organ_drive=0.0, sphincter_relax=0.0)

    n = int(hours * 3600 / dt)
    next_void = interval_h * 3600
    series, voids, residuals, void_pressures = [], [], [], []
    void_until = -1.0
    worst_ad = 0.0
    stride = max(1, n // 480)
    for i in range(n):
        t = i * dt
        if interval_h > 0 and t >= next_void:
            void_until = t + 120          # 2-min void window
            voids.append(round(t / 3600, 2))
            next_void += interval_h * 3600
        voiding = t < void_until
        just_closed = (not voiding) and abs(t - void_until) < dt
        cmd = AutonomicCommand.VOID if voiding else AutonomicCommand.STORE
        bladder.step(drive if voiding else store, cmd, dt)
        if voiding:
            void_pressures.append(bladder.pressure_cmH2O)
        if just_closed:
            residuals.append(bladder.volume_ml)        # post-void residual volume
        ad_rise = max(0.0, bladder.pressure_cmH2O - AD_PRESSURE_TRIGGER_cmH2O) * 1.5
        worst_ad = max(worst_ad, ad_rise)
        if i % stride == 0:
            series.append({"h": round(t / 3600, 2),
                           "volume": round(bladder.volume_ml, 1),
                           "pressure": round(bladder.pressure_cmH2O, 1)})
    residual = sum(residuals) / len(residuals) if residuals else bladder.volume_ml
    peak_void = max(void_pressures) if void_pressures else 0.0
    return {"series": series, "voids": voids,
            "peak_pressure": round(peak_void, 1),     # peak DURING voids (the DSD danger)
            "residual_ml": round(residual, 1),         # mean post-void residual
            "worst_ad_rise": round(worst_ad, 1),
            "safe": bool(peak_void < SAFE_VOID_PRESSURE_cmH2O + 10
                         and worst_ad < AD_BP_RISE_LIMIT)}


def simulate_training_curve(weeks: int = 8) -> dict:
    """Multi-week TRAINING trend (activity-dependent plasticity HYPOTHESIS): with a
    daily scheduled regimen, modeled capacity rises and residual/peak pressure fall.
    Illustrative — a research prediction to test, not a clinical claim."""
    rows = []
    for w in range(weeks + 1):
        trained = 1 - pow(2.718, -w / 3.0)        # saturating learning curve
        day = simulate_bladder_day(trained=trained)
        rows.append({"week": w,
                     "capacity_ml": round(450 + 150 * trained),
                     "residual_ml": day["residual_ml"],
                     "peak_pressure": day["peak_pressure"],
                     "ad_rise": day["worst_ad_rise"]})
    gain = round(150 / 450 * (1 - pow(2.718, -weeks / 3.0)) * 100)
    return {"weeks": rows,
            "summary": {"capacity_gain_pct": gain,
                        "final_peak_pressure": rows[-1]["peak_pressure"]}}


def schedule_24h() -> dict:
    """The day's autonomic schedule the device would run automatically."""
    events = []
    for h in range(0, 24):
        if h % 4 == 0:
            events.append({"h": h, "function": "bladder", "label": "Bladder void (coordinated)"})
    events.append({"h": 8, "function": "bowel", "label": "Bowel program"})
    events.sort(key=lambda e: e["h"])
    return {"protocols": {k: p.as_dict() for k, p in PROTOCOLS.items()}, "events": events}
