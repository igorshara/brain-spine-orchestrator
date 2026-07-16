"""Runtime wiring: assemble the six layers into one closed-loop tick system.

Складання замкнутого контуру. Цей модуль — «клей» між шарами (його немає у списку
шарів канону, бо це інфраструктура, а не шар обробки). Порядок тіку відтворює
пряму дугу; зворотний зв'язок приходить із затримкою в один крок (реалістично).

Ключова деталь: між ефекторами і тілом стоїть МОДЕЛЬ СПИННОГО МОЗКУ
(``SpinalCord``) — вона проводить КОЖНУ StimCommand через safety-супервізор, а
тоді через ПРЯМУ криву рекрутингу переводить (можливо обрізану) амплітуду назад
у досягнуту активацію. Тому будь-яке обрізання safety стає видимим у русі.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .biomech.base import BioMechModel
from .biomech.kinematic import KinematicModel
from .bus import Bus, TickLoop
from .config.muscles import ANTAGONIST, CHANNEL_TO_GROUP, MUSCLE_GROUPS
from .decoder_stub import DecoderStub
from .degradation import FatigueModel
from .effectors import Effectors
from .feedback import Feedback
from .orchestrator import Orchestrator
from .safety import SafetySupervisor


class SpinalCord:
    """Stim -> (safety) -> achieved activation -> body input.

    Topics: in ``stim_commands`` -> out ``activations`` (dict group_id->0..1)
    and ``applied_commands`` (list of post-safety StimCommand) plus
    ``safety_events`` (list of verdict reasons that were not plain "ok").
    """

    IN_COMMANDS = "stim_commands"
    OUT_ACT = "activations"
    OUT_APPLIED = "applied_commands"
    OUT_EVENTS = "safety_events"

    def __init__(self, safety: SafetySupervisor, fatigue: FatigueModel | None = None,
                 coupling: float = 0.0, emd_s: float = 0.0) -> None:
        self.safety = safety
        self.fatigue = fatigue
        # Current-spread coupling: fraction of a group's recruitment that spills
        # into its antagonist (co-activation), reducing net joint torque. A real
        # EES phenomenon between neighbouring contacts. ILLUSTRATIVE.
        self.coupling = coupling
        # Electromechanical delay (EMD): first-order lag between the stim command
        # and the achieved activation/force (~50-120 ms in real muscle). Default
        # 0.0 keeps the legacy instant response; >0 models the lag that
        # feed-forward ("shadow step") control is designed to anticipate.
        self.emd_s = emd_s
        self._act_lp: dict[str, float] = dict.fromkeys(MUSCLE_GROUPS, 0.0)

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        commands = bus.latest(self.IN_COMMANDS) or []
        activations: dict[str, float] = dict.fromkeys(MUSCLE_GROUPS, 0.0)
        applied = []
        events = []
        for cmd in commands:
            verdict = self.safety.check(cmd)
            safe = verdict.command
            applied.append(safe)
            if verdict.reason and verdict.reason != "ok":
                events.append((safe.channel_id, verdict.reason))
            gid = CHANNEL_TO_GROUP.get(safe.channel_id)
            if gid is not None and verdict.approved:
                curve = MUSCLE_GROUPS[gid].recruitment
                # Fatigue/drift act on the INPUT (effective current): a fatigued
                # circuit needs MORE stimulation for the same activation. This is
                # physiologically truer than capping output, and it makes the
                # shortfall recoverable by raising amplitude — until safety clamps.
                eff_amp = safe.amplitude_mA
                if self.fatigue is not None:
                    eff_amp *= (1.0 - self.fatigue.degradation(gid, t))
                activations[gid] = curve.activation(eff_amp)
            # blocked/disapproved -> activation stays 0 for that group

        # Current-spread: add antagonist co-activation, then update fatigue on the
        # ACTUAL (coupled) activation each group ends up producing.
        if self.coupling > 0.0:
            base = dict(activations)
            for gid, ant in ANTAGONIST.items():
                activations[gid] = min(1.0, base[gid] + self.coupling * base.get(ant, 0.0))
        # Electromechanical delay: low-pass the achieved activation toward the
        # commanded one with time constant emd_s. Force lags the command, so a
        # reactive correction issued only after a sensed drag arrives late.
        if self.emd_s > 0.0:
            alpha = dt / (self.emd_s + dt)
            for gid, a in activations.items():
                self._act_lp[gid] += alpha * (a - self._act_lp[gid])
                activations[gid] = self._act_lp[gid]

        if self.fatigue is not None:
            for gid, a in activations.items():
                if a > 0.0:
                    self.fatigue.update(gid, a, dt)

        # Safety maintenance: cool thermal proxy, enforce liveness watchdog.
        zeroed = self.safety.tick(t, dt)
        for ch in zeroed:
            gid = CHANNEL_TO_GROUP.get(ch)
            if gid is not None:
                activations[gid] = 0.0

        bus.publish(self.OUT_ACT, activations)
        bus.publish(self.OUT_APPLIED, applied)
        bus.publish(self.OUT_EVENTS, events)


class HandPacer:
    """The patient's arms set the step cadence. Emits a ``hand_step`` trigger at
    the intended cadence — a high-sparing, reliable rhythm the leg decoder may
    lack. The orchestrator (cadence_source="manual") phase-locks the gait to it.

    ``cadence_fn(t)`` returns the intended cadence in steps/min at time t.
    """

    OUT = "hand_step"

    def __init__(self, cadence_fn) -> None:
        self.cadence_fn = cadence_fn
        self._id = 0
        self._next_t = 0.0

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        if t >= self._next_t:
            self._id += 1
            bus.publish(self.OUT, {"id": self._id, "t": t})
            cad = max(1e-6, float(self.cadence_fn(t)))
            self._next_t = t + 60.0 / cad      # one step per 60/cadence seconds


class Body:
    """Wraps a BioMechModel as a tick component. Reads ``activations``,
    publishes ``sensor_frame``."""

    IN_ACT = "activations"
    OUT_FRAME = "sensor_frame"

    def __init__(self, model: BioMechModel) -> None:
        self.model = model

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        activations = bus.latest(self.IN_ACT) or {}
        frame = self.model.step(activations, t, dt)
        bus.publish(self.OUT_FRAME, frame)


class Recorder:
    """Snapshots key signals each tick for logging / visualization."""

    def __init__(self, body: Body, cord: SpinalCord | None = None,
                 effectors: Effectors | None = None) -> None:
        self.body = body
        self.cord = cord
        self.effectors = effectors
        self.t: list[float] = []
        self.pose: list[dict] = []
        self.frames: list = []
        self.activations: list[dict] = []
        self.targets: list = []
        self.applied: list = []
        self.gait_phase: list[dict] = []
        self.gait_state: list = []
        self.safety_events: list = []
        self.gains: list[dict] = []
        self.fatigue: list[dict] = []

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        self.t.append(t)
        self.pose.append(self.body.model.pose())
        self.frames.append(bus.latest("sensor_frame"))
        self.activations.append(bus.latest("activations") or {})
        self.targets.append(bus.latest("muscle_targets") or [])
        self.applied.append(bus.latest("applied_commands") or [])
        self.gait_phase.append(bus.latest("gait_phase") or {})
        self.gait_state.append(bus.latest("gait_state"))
        self.gains.append(dict(self.effectors.gains) if self.effectors else {})
        if self.cord is not None and self.cord.fatigue is not None:
            self.fatigue.append({g: self.cord.fatigue.level(g) for g in MUSCLE_GROUPS})
        else:
            self.fatigue.append({})
        ev = bus.latest("safety_events") or []
        if ev:
            self.safety_events.extend((t, ch, r) for ch, r in ev)


@dataclass
class System:
    """Bundle of the assembled components for easy access in scenarios/tests."""

    loop: TickLoop
    bus: Bus
    decoder: DecoderStub
    orchestrator: Orchestrator
    effectors: Effectors
    safety: SafetySupervisor
    cord: SpinalCord
    body: Body
    feedback: Feedback
    recorder: Recorder
    model: BioMechModel = field(default=None)  # type: ignore[assignment]
    adaptation: object = None

    def run(self, duration_s: float) -> Recorder:
        self.loop.run(duration_s)
        return self.recorder


def build_system(
    schedule,
    dt: float = 0.005,
    model: BioMechModel | None = None,
    record: bool = True,
    fatigue: FatigueModel | None = None,
    adapt: bool = False,
    sensor_corruptor=None,
    policy=None,
    coupling: float = 0.0,
    emd_s: float = 0.0,
    hand_cadence=None,
    safety: SafetySupervisor | None = None,
    bus: Bus | None = None,
    loop: TickLoop | None = None,
) -> System:
    """Wire decoder -> orchestrator -> effectors -> cord(+safety) -> body ->
    [sensor corruption] -> feedback into a single deterministic tick loop.

    Tick order is the forward arc; feedback (gait_state/corrections) is read by
    the orchestrator on the following tick, i.e. a one-step closed-loop delay.

    ``fatigue`` injects a plant-degradation model (muscle fatigue + drift).
    ``adapt`` enables the slow Layer-4 OnlineAdaptation that compensates it.
    ``sensor_corruptor`` (a SensorCorruptor) adds noise/dropout before Layer 3.
    """
    # bus/loop/safety can be SHARED (passed in) so locomotion and autonomic run on
    # ONE substrate; default None keeps every existing caller building its own.
    if bus is None:
        bus = Bus()
        bus.enable_recording(False)
    if loop is None:
        loop = TickLoop(dt=dt, bus=bus)

    model = model or KinematicModel()
    safety = safety or SafetySupervisor()

    decoder = DecoderStub(schedule)
    orchestrator = Orchestrator(cadence_source="manual" if hand_cadence is not None else "intent")
    pacer = HandPacer(hand_cadence) if hand_cadence is not None else None
    effectors = Effectors()
    cord = SpinalCord(safety, fatigue=fatigue, coupling=coupling, emd_s=emd_s)
    body = Body(model)
    feedback = Feedback()
    recorder = Recorder(body, cord=cord, effectors=effectors)

    adaptation = None
    if policy is not None:
        from .learned_adaptation import LearnedAdaptation

        adaptation = LearnedAdaptation(effectors, policy)
    elif adapt:
        from .adaptation import OnlineAdaptation

        adaptation = OnlineAdaptation(effectors, enabled=True)

    # Order: decoder, orchestrator, effectors, cord, body, [corruptor], feedback,
    # [adaptation]. Corruption sits between the plant and sensor fusion.
    components = [decoder]
    if pacer is not None:                 # arm rhythm must publish before the conductor
        components.append(pacer)
    components += [orchestrator, effectors, cord, body]
    if sensor_corruptor is not None:
        components.append(sensor_corruptor)
    components.append(feedback)
    if adaptation is not None:
        components.append(adaptation)
    for c in components:
        loop.add(c)
    if record:
        loop.add(recorder)

    return System(
        loop=loop,
        bus=bus,
        decoder=decoder,
        orchestrator=orchestrator,
        effectors=effectors,
        safety=safety,
        cord=cord,
        body=body,
        feedback=feedback,
        recorder=recorder,
        model=model,
        adaptation=adaptation,
    )
