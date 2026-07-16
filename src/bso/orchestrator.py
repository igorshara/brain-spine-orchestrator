"""Layer 1 — Orchestrator (the conductor): a phase-based CPG + state machine.

Шар 1 — диригент. Перетворює Intent у фазову модель ходи (CPG / скінченний
автомат) і розкладає на цільові активації м'язових груп із таймінговими вікнами.
Тримає внутрішній фазовий годинник циклу ходи.

Фізіологічно коректно (канон §2): ми моделюємо ходу ФАЗОВО (CPG-подібно), а не як
прямий мапінг «м'яз → напруга». Кожна група має профіль активації над фазою
циклу; ліва і права ноги зсунуті на пів-цикла.

This layer is a deterministic controller. No LLM is ever in this real-time path
(canon §1.6).
"""

from __future__ import annotations

import math

from .bus import Bus
from .config.muscles import GROUP_IDS
from .schemas import Intent, MuscleTarget, Phase


def _gauss_wrap(p: float, mu: float, sigma: float) -> float:
    """Gaussian bump over the unit circle (phase wraps at 1.0)."""
    d = abs(p - mu)
    d = min(d, 1.0 - d)
    return math.exp(-0.5 * (d / sigma) ** 2)


# --- Per-leg activation profiles over the gait cycle phase p in [0,1). ---
# Stance ~ [0.0, 0.6), swing ~ [0.6, 1.0). ILLUSTRATIVE timing/amplitudes.
def _leg_profile(p: float) -> dict[str, float]:
    # Stance ~ [0.0, 0.6) (foot planted, knee extended); swing ~ [0.6, 1.0)
    # (knee flexes to lift the foot, then re-extends for heel strike).
    return {
        # Hip: extends through stance (drives body forward), flexes in swing.
        "hip_ext": 0.8 * _gauss_wrap(p, 0.30, 0.16),
        "hip_flex": 0.8 * _gauss_wrap(p, 0.80, 0.12),
        # Knee: extended for support across stance and at terminal swing;
        # one clean flexion burst through swing to clear the foot.
        "knee_ext": 0.7 * _gauss_wrap(p, 0.20, 0.15) + 0.5 * _gauss_wrap(p, 0.98, 0.06),
        "knee_flex": 0.85 * _gauss_wrap(p, 0.75, 0.13),
        # Ankle: plantarflexion push-off at terminal stance; dorsiflexion in
        # swing for foot clearance (counters foot-drop).
        "ankle_plantar": 0.7 * _gauss_wrap(p, 0.55, 0.08),
        "ankle_dorsi": 0.7 * _gauss_wrap(p, 0.80, 0.12),
    }


def _phase_of(p: float) -> Phase:
    if p < 0.6:
        return Phase.STANCE
    return Phase.SWING


class Orchestrator:
    """Reads ``intent`` (+ optional ``gait_state``/``corrections``), advances an
    internal phase clock, publishes a list of :class:`MuscleTarget` on
    ``muscle_targets``. Also publishes its intended ``gait_phase`` for telemetry.
    """

    IN_INTENT = "intent"
    IN_GAIT = "gait_state"
    IN_CORR = "corrections"
    IN_HAND = "hand_step"
    OUT_TARGETS = "muscle_targets"
    OUT_PHASE = "gait_phase"

    def __init__(self, cadence_source: str = "intent") -> None:
        self.cycle_phase = 0.0  # 0..1, left leg reference
        self.cadence = 0.0  # steps/min, 0 when not walking
        # "intent": cadence from the (possibly unreliable) leg-intent decoder.
        # "manual": cadence is phase-locked to the patient's ARM rhythm — the
        # high-sparing hand-step triggers set the pace (the "hand pacer" idea).
        self.cadence_source = cadence_source
        self._manual_period = 1.5      # s, inferred from arm step interval
        self._last_trig_t: float | None = None
        self._last_trig_id: int | None = None

    # cadence from desired speed (ILLUSTRATIVE mapping)
    @staticmethod
    def _cadence_for(speed: float) -> float:
        speed = max(0.0, min(1.0, speed))
        return 40.0 + 60.0 * speed  # 40..100 steps/min

    def _targets_for_mode(self, intent: Intent, t: float) -> list[MuscleTarget]:
        mode = intent.mode
        targets: list[MuscleTarget] = []

        def emit(gid: str, act: float, window: tuple[float, float]) -> None:
            targets.append(
                MuscleTarget(
                    t=t,
                    group_id=gid,
                    desired_activation=max(0.0, min(1.0, act)),
                    phase_window=window,
                )
            )

        if mode.value == "idle":
            for gid in GROUP_IDS:
                emit(gid, 0.0, (0.0, 1.0))
            return targets

        if mode.value == "sit":
            # Sustained hip/knee flexion, minimal extensor tone, trunk stable.
            for side in ("L", "R"):
                emit(f"{side}_hip_flex", 0.4, (0.0, 1.0))
                emit(f"{side}_knee_flex", 0.5, (0.0, 1.0))
                emit(f"{side}_trunk_stab", 0.5, (0.0, 1.0))
            return targets

        if mode.value == "stand":
            # Bilateral extensor + ankle + trunk tone, no rhythm.
            for side in ("L", "R"):
                emit(f"{side}_hip_ext", 0.55, (0.0, 1.0))
                emit(f"{side}_knee_ext", 0.6, (0.0, 1.0))
                emit(f"{side}_ankle_plantar", 0.25, (0.0, 1.0))
                emit(f"{side}_trunk_stab", 0.7, (0.0, 1.0))
            return targets

        # WALK / TURN / STAIRS : rhythmic CPG.
        gain_stairs = 1.0
        asym = {"L": 1.0, "R": 1.0}
        if mode.value in ("stairs_up", "stairs_down"):
            gain_stairs = 1.25  # higher flexion to clear steps
        if mode.value == "turn_left":
            asym = {"L": 0.8, "R": 1.15}
        elif mode.value == "turn_right":
            asym = {"L": 1.15, "R": 0.8}

        for side, leg_phase in (("L", self.cycle_phase), ("R", (self.cycle_phase + 0.5) % 1.0)):
            prof = _leg_profile(leg_phase)
            g = asym[side]
            for action, act in prof.items():
                a = act * g
                if action in ("hip_flex", "knee_flex", "ankle_dorsi"):
                    a *= gain_stairs
                emit(f"{side}_{action}", a, (0.0, 1.0))
            # Trunk stabilizers always on during locomotion.
            emit(f"{side}_trunk_stab", 0.6, (0.0, 1.0))
        return targets

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        intent: Intent | None = bus.latest(self.IN_INTENT)
        if intent is None:
            return

        # Advance the phase clock only while walking-like.
        if intent.mode.value in ("walk", "turn_left", "turn_right", "stairs_up", "stairs_down"):
            if self.cadence_source == "manual":
                # Phase-lock the gait clock to the patient's arm rhythm: each
                # hand-step trigger re-syncs the phase to a heel-strike boundary
                # and re-estimates the period — independent of the leg decoder.
                trig = bus.latest(self.IN_HAND)
                if trig and trig.get("id") != self._last_trig_id:
                    self._last_trig_id = trig["id"]
                    if self._last_trig_t is not None:
                        interval = t - self._last_trig_t
                        if 0.2 < interval < 3.0:        # one step = half a cycle
                            self._manual_period = 2.0 * interval
                    self._last_trig_t = t
                    self.cycle_phase = 0.0 if trig["id"] % 2 == 0 else 0.5
                self.cadence = 120.0 / max(self._manual_period, 1e-6)
                self.cycle_phase = (self.cycle_phase + dt / self._manual_period) % 1.0
            else:
                self.cadence = self._cadence_for(intent.speed)
                # cycle = 2 steps; period T = 120/cadence seconds.
                period = 120.0 / max(self.cadence, 1e-6)
                self.cycle_phase = (self.cycle_phase + dt / period) % 1.0
        else:
            self.cadence = 0.0
            self.cycle_phase = 0.0

        targets = self._targets_for_mode(intent, t)

        # Apply feedback corrections (closed loop): scale named groups.
        corr: dict[str, float] | None = bus.latest(self.IN_CORR)
        if corr:
            for mt in targets:
                if mt.group_id in corr:
                    mt.desired_activation = max(
                        0.0, min(1.0, mt.desired_activation * corr[mt.group_id])
                    )

        bus.publish(self.OUT_TARGETS, targets)
        bus.publish(
            self.OUT_PHASE,
            {
                "cycle_phase": self.cycle_phase,
                "cadence": self.cadence,
                "phase_left": _phase_of(self.cycle_phase).value,
                "phase_right": _phase_of((self.cycle_phase + 0.5) % 1.0).value,
            },
        )
