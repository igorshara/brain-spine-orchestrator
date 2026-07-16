"""Hill-type muscle model — the physiology that turns activation into force.

Модель м'яза Хілла: те, що перетворює активацію на СИЛУ з реалістичною динамікою.
Додає фізіологію, якої не було в миттєвому мапінгу «активація→рух»:

  1. **Динаміка активації** — збудження не вмикає силу миттєво; активація наростає
     й спадає з різними сталими часу (швидше активується, повільніше розслабляється).
  2. **Сила-довжина (force-length)** — м'яз сильніший біля оптимальної довжини
     волокна, слабший у крайніх положеннях суглоба.
  3. **Сила-швидкість (force-velocity)** — менша сила при швидкому вкороченні
     (концентрика), більша при розтягненні (ексцентрика).

Це і є те, що дала б валідована модель OpenSim/Thelen; тут реалізовано прозоро в
numpy, щоб чисто інтегрувати й тестувати. Усе ILLUSTRATIVE (нормовані величини).
OpenSim 4.6 доступний для майбутньої повної м'язово-скелетної моделі.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class HillMuscle:
    """Single Hill-type muscle. Normalized units (force 0..~1.5·Fmax, length ~1)."""

    tau_act: float = 0.012     # activation time constant (s)
    tau_deact: float = 0.050   # deactivation is slower than activation
    opt_length: float = 1.0    # optimal fibre length (normalized)
    fl_width: float = 0.45     # force-length curve width
    v_max: float = 8.0         # max shortening velocity (norm length/s)
    f_max: float = 1.0         # peak isometric force
    activation: float = 0.0    # state, 0..1

    def update_activation(self, excitation: float, dt: float) -> None:
        u = max(0.0, min(1.0, excitation))
        tau = self.tau_act if u >= self.activation else self.tau_deact
        self.activation += (u - self.activation) / tau * dt
        self.activation = max(0.0, min(1.0, self.activation))

    def force_length(self, length: float) -> float:
        return math.exp(-((length - self.opt_length) / self.fl_width) ** 2)

    def force_velocity(self, velocity: float) -> float:
        # velocity > 0 = shortening (concentric, weaker); < 0 = lengthening
        # (eccentric, stronger, plateauing ~1.4).
        if velocity >= 0:
            return max(0.0, (self.v_max - velocity) / (self.v_max + 4.0 * velocity))
        return min(1.4, 1.0 + 0.3 * (-velocity) / self.v_max)

    def passive_force(self, length: float) -> float:
        if length <= self.opt_length:
            return 0.0
        return min(1.0, ((length - self.opt_length) / self.fl_width) ** 2 * 0.5)

    def force(self, length: float, velocity: float) -> float:
        active = self.activation * self.f_max * self.force_length(length) \
            * self.force_velocity(velocity)
        return active + self.passive_force(length)
