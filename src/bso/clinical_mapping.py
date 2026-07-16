"""Clinical decision-support for stimulation mapping — clinician-in-the-loop.

Інструмент ПІДТРИМКИ РІШЕНЬ для клініциста (напр. the clinical partner з the partner stimulator).
Замість ручного перебору сотень конфігурацій клініцист на кожному кроці вводить,
яку конфігурацію спробував і яку відповідь побачив (активація цільового м'яза,
комфорт, побічне), а інструмент через Gaussian-Process Bayesian Optimization
пропонує НАСТУПНУ найінформативнішу конфігурацію — у межах безпеки.

КРИТИЧНО — межі відповідальності:
  * Цей інструмент НІЧОГО не стимулює і НЕ керує жодним приладом. Він лише РАДИТЬ
    параметри. Усю стимуляцію виконує клініцист через сертифікований програматор.
  * Кожна запропонована конфігурація проходить хард-ліміти safety (config/limits).
  * Клініцист завжди має останнє слово; інструмент — асистент, не лікар.

Експорт: впорядкований звіт сесії (що пробували, відповіді, рекомендована програма)
для перенесення у програматор. Усе ILLUSTRATIVE до валідації на реальних відповідях.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .bopt import GaussianProcess
from .config.limits import LIMITS


@dataclass
class StimConfig:
    """A candidate stimulation setting (within safety limits)."""

    contact: int
    amplitude_mA: float
    pulse_width_us: float
    frequency_Hz: float = 40.0

    def within_limits(self) -> bool:
        L = LIMITS
        return (L.amplitude_min_mA <= self.amplitude_mA <= L.amplitude_max_mA
                and L.pulse_width_min_us <= self.pulse_width_us <= L.pulse_width_max_us
                and L.frequency_min_Hz <= self.frequency_Hz <= L.frequency_max_Hz
                and self.amplitude_mA * self.pulse_width_us / 1000.0
                <= L.charge_per_phase_max_uC + 1e-9)


@dataclass
class Observation:
    config: StimConfig
    response: float  # clinician-scored quality, e.g. target activation − discomfort (0..1)
    note: str = ""


@dataclass
class ClinicalMappingSession:
    """Stateful GP-BO decision-support session for one mapping target.

    Usage (clinician-in-the-loop):
        s = ClinicalMappingSession(n_contacts=16, target="left knee flexion")
        cfg = s.suggest_next()          # tool proposes a safe config to TRY
        # clinician applies cfg via the official programmer, observes response
        s.record(cfg, response=0.6, note="visible knee flexion, comfortable")
        ...                              # repeat
        print(s.report())               # export recommended program
    """

    n_contacts: int = 16
    target: str = "target muscle"
    amp_grid: tuple = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
    pw_grid: tuple = (120.0, 200.0, 300.0, 400.0)
    frequency_Hz: float = 40.0
    beta: float = 2.0
    observations: list[Observation] = field(default_factory=list)
    _candidates: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        cands = []
        for c in range(self.n_contacts):
            for a in self.amp_grid:
                for p in self.pw_grid:
                    cfg = StimConfig(c, a, p, self.frequency_Hz)
                    if cfg.within_limits():
                        cands.append([c, a, p])
        self._candidates = np.array(cands, float)
        # normalized features for the GP
        self._norm = np.column_stack([
            self._candidates[:, 0] / max(self.n_contacts - 1, 1),
            self._candidates[:, 1] / LIMITS.amplitude_max_mA,
            self._candidates[:, 2] / LIMITS.pulse_width_max_us,
        ])
        # Clinically-sensible warm-up: a coarse contact sweep at a moderate,
        # supra-threshold-but-comfortable setting, so the GP sees the contact
        # landscape before refining (mirrors how a clinician ramps then compares).
        amp0 = min(self.amp_grid, key=lambda a: abs(a - 5.0))
        pw0 = min(self.pw_grid, key=lambda p: abs(p - 300.0))
        sweep = sorted({int(round(c)) for c in np.linspace(0, self.n_contacts - 1, 6)})
        self._warmup = [StimConfig(c, amp0, pw0, self.frequency_Hz) for c in sweep]

    def _cfg(self, row) -> StimConfig:
        return StimConfig(int(round(row[0])), float(row[1]), float(row[2]), self.frequency_Hz)

    def _tried_mask(self) -> set:
        return {(o.config.contact, o.config.amplitude_mA, o.config.pulse_width_us)
                for o in self.observations}

    def suggest_next(self) -> StimConfig:
        """Propose the next configuration to try (UCB GP-BO), within safety limits.
        With <2 observations, proposes a low-amplitude exploratory point."""
        tried = self._tried_mask()
        # Warm-up: coarse contact sweep first (informative, comfortable).
        for cfg in self._warmup:
            if (cfg.contact, cfg.amplitude_mA, cfg.pulse_width_us) not in tried:
                return cfg
        X = np.array([[o.config.contact / max(self.n_contacts - 1, 1),
                       o.config.amplitude_mA / LIMITS.amplitude_max_mA,
                       o.config.pulse_width_us / LIMITS.pulse_width_max_us]
                      for o in self.observations])
        y = np.array([o.response for o in self.observations])
        gp = GaussianProcess()
        gp.fit(X, y)
        mu, var = gp.predict(self._norm)
        acq = mu + self.beta * np.sqrt(var)
        for i, row in enumerate(self._candidates):
            if (int(round(row[0])), row[1], row[2]) in tried:
                acq[i] = -np.inf
        cfg = self._cfg(self._candidates[int(np.argmax(acq))])
        assert cfg.within_limits()  # never propose an unsafe config
        return cfg

    def record(self, config: StimConfig, response: float, note: str = "") -> None:
        self.observations.append(Observation(config, float(np.clip(response, 0.0, 1.0)), note))

    def best(self) -> Observation | None:
        return max(self.observations, key=lambda o: o.response) if self.observations else None

    def report(self) -> str:
        lines = [
            f"# Stimulation mapping session — target: {self.target}",
            "DECISION SUPPORT ONLY — clinician applies settings via the official "
            "programmer. Tool does not stimulate. Values within safety limits.",
            "",
            f"Configurations tried: {len(self.observations)}",
            "",
            "| # | contact | amp (mA) | PW (us) | freq (Hz) | response | note |",
            "|---|---|---|---|---|---|---|",
        ]
        for i, o in enumerate(self.observations, 1):
            c = o.config
            lines.append(f"| {i} | {c.contact} | {c.amplitude_mA:.1f} | {c.pulse_width_us:.0f} "
                         f"| {c.frequency_Hz:.0f} | {o.response:.2f} | {o.note} |")
        b = self.best()
        if b:
            c = b.config
            lines += ["", "## Recommended program (for clinician review)",
                      f"- contact **{c.contact}**, amplitude **{c.amplitude_mA:.1f} mA**, "
                      f"pulse width **{c.pulse_width_us:.0f} us**, frequency "
                      f"**{c.frequency_Hz:.0f} Hz**  (response {b.response:.2f})",
                      f"- charge/phase {c.amplitude_mA * c.pulse_width_us / 1000:.2f} uC "
                      f"(limit {LIMITS.charge_per_phase_max_uC:.1f} uC)"]
        return "\n".join(lines)
