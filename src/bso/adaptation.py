"""Layer 4 — Adaptation (slow, between sessions / steps).

Шар 4 — повільна адаптація: компенсація дрейфу параметрів, втоми, рекалібрування
recruitment-кривих, налаштування «під день». Працює НЕ в реальному часі
моторного циклу (канон §3, Layer 4) — це офлайн-оптимізація між сесіями.

Тут реалізовано просту, прозору версію: за метриками якості ходи з сесії шар
повертає дельти параметрів (підсилення груп зі слабким рекрутингом, компенсація
накопиченої втоми). Згодом тут доречний RL.
"""

from __future__ import annotations

from .bus import Bus
from .runtime import Recorder
from .schemas import AdaptationUpdate


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


class OnlineAdaptation:
    """Layer 4 — SLOW closed-loop adaptation (between gait cycles, NOT in the
    ms motor loop). Deterministic integral controller, no LLM.

    Повільна адаптація в реальній сесії: порівнює ЗАДАНУ активацію (від диригента)
    з ДОСЯГНУТОЮ (після рекрутингу й деградації), накопичує помилку по групах і
    раз на ``interval`` секунд (порядку тривалості кроку) піднімає підсилення
    ефекторів, щоб закрити розрив, спричинений втомою/дрейфом. Safety все одно
    обрізає результат — адаптація не може вийти за межі.
    """

    IN_TARGETS = "muscle_targets"
    IN_ACT = "activations"
    OUT_TELEMETRY = "adaptation"

    def __init__(self, effectors, interval: float = 0.4, k: float = 0.8,
                 gain_min: float = 0.5, gain_max: float = 3.0, enabled: bool = True) -> None:
        self.effectors = effectors
        self.interval = interval
        self.k = k
        self.gain_min = gain_min
        self.gain_max = gain_max
        self.enabled = enabled
        self._sum_err: dict[str, float] = {}
        self._weight: dict[str, float] = {}
        self._accum_t = 0.0

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        if not self.enabled:
            return
        targets = bus.latest(self.IN_TARGETS) or []
        achieved = bus.latest(self.IN_ACT) or {}
        for mt in targets:
            d = mt.desired_activation
            if d <= 0.1:  # ignore near-silent groups (noise)
                continue
            a = achieved.get(mt.group_id, 0.0)
            self._sum_err[mt.group_id] = self._sum_err.get(mt.group_id, 0.0) + (d - a) * d
            self._weight[mt.group_id] = self._weight.get(mt.group_id, 0.0) + d

        self._accum_t += dt
        if self._accum_t < self.interval:
            return
        self._accum_t = 0.0
        for gid, w in self._weight.items():
            if w <= 1e-6:
                continue
            avg_err = self._sum_err.get(gid, 0.0) / w  # desired-minus-achieved
            g = self.effectors.gains.get(gid, 1.0) + self.k * avg_err
            self.effectors.gains[gid] = max(self.gain_min, min(self.gain_max, g))
        self._sum_err.clear()
        self._weight.clear()
        bus.publish(self.OUT_TELEMETRY, dict(self.effectors.gains))


class Adaptation:
    """Offline analyzer producing AdaptationUpdate deltas from a session log."""

    def __init__(self, fatigue_drift: float = 0.0) -> None:
        # fatigue_drift models recruitment weakening accumulated over a session.
        self.fatigue_drift = fatigue_drift

    def session_metrics(self, rec: Recorder) -> dict[str, float]:
        """Aggregate simple quality metrics from a recorded session."""
        balance = [g.balance_ok for g in rec.gait_state if g is not None]
        cadences = [g.cadence for g in rec.gait_state if g is not None]
        # Symmetry over the whole session via per-leg support impulse (∫GRF dt).
        # This avoids the swing-phase artifact of instantaneous L/R ratios.
        imp_l = sum(f.grf.get("L", 0.0) for f in rec.frames if f is not None)
        imp_r = sum(f.grf.get("R", 0.0) for f in rec.frames if f is not None)
        tot = imp_l + imp_r
        imbalance = abs(imp_l - imp_r) / tot if tot > 1e-6 else 0.0
        return {
            "balance_ok_ratio": (sum(balance) / len(balance)) if balance else 0.0,
            "mean_cadence": _mean(cadences),
            "mean_grf_imbalance": imbalance,
            "impulse_left": imp_l,
            "impulse_right": imp_r,
            "n_safety_events": float(len(rec.safety_events)),
        }

    def propose(self, rec: Recorder, t: float = 0.0) -> list[AdaptationUpdate]:
        """Return parameter-delta proposals for Layers 1-2 based on the session.

        Transparent rules (ILLUSTRATIVE):
          * compensate accumulated fatigue by raising target activation gain,
          * if gait is asymmetric, nudge the weaker side up.
        """
        m = self.session_metrics(rec)
        updates: list[AdaptationUpdate] = []

        if self.fatigue_drift > 0.0:
            updates.append(
                AdaptationUpdate(
                    t=t,
                    target_id="global_activation_gain",
                    param_deltas={"gain": round(self.fatigue_drift, 4)},
                    rationale=(
                        f"compensate fatigue drift {self.fatigue_drift:.3f} measured "
                        f"over session"
                    ),
                )
            )

        if m["mean_grf_imbalance"] > 0.15:
            # Determine weaker side from total support impulse.
            weak = "L" if m["impulse_left"] < m["impulse_right"] else "R"
            updates.append(
                AdaptationUpdate(
                    t=t,
                    target_id=f"{weak}_side_extensor_gain",
                    param_deltas={"gain": 0.1},
                    rationale=(
                        f"gait asymmetry {m['mean_grf_imbalance']:.2f}; "
                        f"boost weaker {weak} side"
                    ),
                )
            )
        return updates
