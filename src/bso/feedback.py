"""Layer 3 — Feedback / Sensor Fusion (closed loop).

Шар 3 — зворотний зв'язок. Зі (симульованих) IMU, кутів суглобів та опорної
реакції (GRF) оцінює фактичну фазу ходи й баланс, детектує помилки (волочіння
стопи, асиметрія, втрата рівноваги) і подає корекцію диригенту й ефекторам.

Тип: легкий оцінювач стану + детектори подій (канон §3, Layer 3). No ML.
Output: ``gait_state`` (GaitState) and ``corrections`` (dict group_id -> gain).
"""

from __future__ import annotations

from .bus import Bus
from .schemas import GaitState, Phase, SensorFrame

# ILLUSTRATIVE thresholds. Two GRF levels form a Schmitt trigger so noise
# around the contact threshold cannot be counted as multiple heel strikes.
GRF_STANCE_HI_N = 180.0  # rising above this enters stance
GRF_STANCE_LO_N = 80.0  # falling below this leaves stance
GRF_STANCE_N = 120.0  # mid level used for phase labelling
TRUNK_BALANCE_DEG = 12.0  # |tilt| beyond this => balance not ok
FOOT_DRAG_ANKLE_DEG = -2.0  # in swing, ankle below this (plantar) => foot drag


class Feedback:
    IN_FRAME = "sensor_frame"
    OUT_STATE = "gait_state"
    OUT_CORR = "corrections"

    def __init__(self, mode: str = "reactive", lead_ms: float = 80.0,
                 pred_gain: float = 1.45, pred_knee_gain: float = 1.15,
                 pred_tail_gain: float = 1.0) -> None:
        # mode: "reactive" (boost dorsiflexion only AFTER foot-drop is sensed),
        #       "predictive" ("shadow step": anticipate swing from the CPG phase
        #       clock and pre-empt dorsiflexion by the electromechanical delay),
        #       "off" (open-loop CPG, no corrections — a clean baseline).
        self.mode = mode
        self.lead_ms = lead_ms              # electromechanical lead, ILLUSTRATIVE
        self.pred_gain = pred_gain          # anticipatory dorsiflexion boost
        self.pred_knee_gain = pred_knee_gain
        # Late-swing attenuation: once the foot has cleared and is descending to
        # heel strike, dorsiflexion is no longer needed and should ease. Cutting
        # it (<1.0) lets the shadow step REDISTRIBUTE effort earlier instead of
        # only adding it — the path to fewer drags at equal/less stimulation.
        self.pred_tail_gain = pred_tail_gain
        self._last_left_strike: float | None = None
        self._cadence = 0.0
        self._period = 1.2  # s, smoothed gait-cycle period
        self._left_in_stance = False
        self._phase_anchor_t = 0.0

    def _update_phase(self, t: float, grf_left: float) -> float:
        # Schmitt-triggered left heel strike => start of a new gait cycle.
        rising = False
        if self._left_in_stance:
            if grf_left < GRF_STANCE_LO_N:
                self._left_in_stance = False
        else:
            if grf_left >= GRF_STANCE_HI_N:
                self._left_in_stance = True
                rising = True
        if rising:
            if self._last_left_strike is not None:
                interval = t - self._last_left_strike
                if 0.2 < interval < 5.0:
                    self._period = 0.7 * self._period + 0.3 * interval
                    self._cadence = 120.0 / self._period  # 2 steps per cycle
            self._last_left_strike = t
            self._phase_anchor_t = t
        frac = (t - self._phase_anchor_t) / max(self._period, 1e-6)
        return frac % 1.0

    @staticmethod
    def _phase(grf: float) -> Phase:
        return Phase.STANCE if grf >= GRF_STANCE_N else Phase.SWING

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        frame: SensorFrame | None = bus.latest(self.IN_FRAME)
        if frame is None:
            return

        grf_l = frame.grf.get("L", 0.0)
        grf_r = frame.grf.get("R", 0.0)
        cycle_phase = self._update_phase(t, grf_l)
        trunk = frame.joint_angles.get("trunk", 0.0)
        balance_ok = abs(trunk) <= TRUNK_BALANCE_DEG

        state = GaitState(
            t=t,
            phase_left=self._phase(grf_l),
            phase_right=self._phase(grf_r),
            cycle_phase=cycle_phase,
            cadence=self._cadence,
            balance_ok=balance_ok,
            trunk_tilt_deg=trunk,
        )
        bus.publish(self.OUT_STATE, state)

        # --- corrections (multiplicative gains, default 1.0) ---
        corr: dict[str, float] = {}

        if self.mode == "predictive":
            # "Shadow step": don't wait for the foot to drop. Read the CPG phase
            # clock (orchestrator publishes it THIS tick, before us) and pre-empt
            # dorsiflexion by the electromechanical lead so the foot is already
            # clearing as swing begins. This routes the command around the lesion
            # in TIME — driven by the intent/phase clock, not by a sensed failure.
            corr.update(self._predictive_corr(bus))
        else:
            # reactive: classic closed loop — correct only after a sensed drag.
            for side, grf in (("L", grf_l), ("R", grf_r)):
                in_swing = grf < GRF_STANCE_N
                ankle = frame.joint_angles.get(f"{side}_ankle", 0.0)
                if in_swing and ankle <= FOOT_DRAG_ANKLE_DEG:
                    corr[f"{side}_ankle_dorsi"] = 1.6
                    corr[f"{side}_knee_flex"] = 1.2

        # Balance stabilisation is common to both closed-loop modes (not the
        # variable under test); "off" stays fully open-loop.
        if self.mode != "off" and not balance_ok:
            corr["L_trunk_stab"] = 1.5
            corr["R_trunk_stab"] = 1.5

        if self.mode == "off":
            corr = {}

        bus.publish(self.OUT_CORR, corr)

    def _predictive_corr(self, bus: Bus) -> dict[str, float]:
        """Anticipatory dorsiflexion from the CPG phase clock: boost each leg in
        a window that opens ``lead_ms`` before its swing onset (phase 0.6)."""
        gp = bus.latest("gait_phase") or {}
        cadence = gp.get("cadence", 0.0)
        if cadence <= 0.0:
            return {}
        cycle_phase = gp.get("cycle_phase", 0.0)
        period = 120.0 / cadence            # seconds per gait cycle (2 steps)
        lead_frac = (self.lead_ms / 1000.0) / max(period, 1e-6)
        w0 = 0.60 - lead_frac               # open the window before swing onset
        w1 = 0.72                           # boost through pre-/early swing
        t0, t1 = 0.85, 1.0                  # late-swing tail to attenuate
        corr: dict[str, float] = {}
        for side, leg_phase in (("L", cycle_phase), ("R", (cycle_phase + 0.5) % 1.0)):
            if w0 <= leg_phase <= w1:
                corr[f"{side}_ankle_dorsi"] = self.pred_gain
                corr[f"{side}_knee_flex"] = self.pred_knee_gain
            elif self.pred_tail_gain != 1.0 and t0 <= leg_phase <= t1:
                corr[f"{side}_ankle_dorsi"] = self.pred_tail_gain
        return corr
