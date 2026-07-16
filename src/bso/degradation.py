"""Plant degradation model: muscle fatigue + slow parameter drift.

Модель деградації плану — те, з чим РЕАЛЬНО бореться адаптивний шар:
  * **Втома** (fatigue): за тривалого використання відповідь м'яза на ту саму
    стимуляцію слабшає; у спокої — відновлюється. Накопичується по групі.
  * **Дрейф** (drift): повільне погіршення рекрутингу за сесію (зсув порогів,
    мікрозміщення електродів, габітуація аферентів) — монотонне в часі.

Це SIM-конструкт (усе ILLUSTRATIVE). Він застосовується в `SpinalCord` ПІСЛЯ
кривої рекрутингу: achieved = recruited * (1 - fatigue - drift). Без адаптації
це призводить до волочіння стопи й падіння якості ходи; адаптивний шар (Layer 4)
підіймає підсилення ефекторів, щоб це компенсувати.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FatigueModel:
    """Per-group fatigue + a global linear drift. All ILLUSTRATIVE."""

    enabled: bool = False
    # Fatigue dynamics: rises with use, recovers at rest.
    fatigue_rate: float = 0.08  # per second at full use
    recovery_rate: float = 0.025  # per second toward rest
    fatigue_max: float = 0.55  # max fractional activation loss from fatigue
    # Drift: linear loss accumulated over the session (capped).
    drift_rate_per_s: float = 0.0  # set >0 to enable monotonic drift
    drift_max: float = 0.35

    _fatigue: dict[str, float] = field(default_factory=dict)
    _t0_seen: bool = False
    _t_start: float = 0.0

    def degradation(self, group_id: str, t: float) -> float:
        """Current fractional loss in [0, ~0.9] for a group at time t."""
        if not self.enabled:
            return 0.0
        if not self._t0_seen:
            self._t_start = t
            self._t0_seen = True
        drift = min(self.drift_max, self.drift_rate_per_s * max(0.0, t - self._t_start))
        return min(0.9, self._fatigue.get(group_id, 0.0) + drift)

    def update(self, group_id: str, use: float, dt: float) -> None:
        """Integrate fatigue for a group given current use (achieved activation)."""
        if not self.enabled:
            return
        f = self._fatigue.get(group_id, 0.0)
        f += dt * (use * self.fatigue_rate - f * self.recovery_rate)
        self._fatigue[group_id] = max(0.0, min(self.fatigue_max, f))

    def level(self, group_id: str) -> float:
        return self._fatigue.get(group_id, 0.0)
