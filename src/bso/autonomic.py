"""Autonomic neuromodulation — bladder, bowel, erectile function.

Автономний шар: відновлення функцій сечового міхура, кишківника та еректильної
функції через ту саму EES-платформу (попереково-крижові контури S2–S4). Для людей
зі спінальною травмою ці функції цінуються нарівні або вище за ходьбу.

Це ОКРЕМИЙ від локомоції контур на спільному стимуляційному+safety субстраті, але
повільний (секунди-хвилини), рефлекторно-станковий, а НЕ ms-моторний. Ключова
проблема SCI — детрузор-сфінктерна дисинергія (DSD): рефлекс скорочує міхур разом
зі сфінктером → високий тиск, неповне спорожнення, ризик для нирок. Координована
нейромодуляція відновлює СИНЕРГІЮ (детрузор скорочується, сфінктер розслабляється).

НАЙКРИТИЧНІШЕ — автономна дисрефлексія (AD): розтягнення нижче рівня травми →
небезпечний стрибок АТ. Тут це моделюється проксі тиску й моніториться.

Це НЕ медичний пристрій. Усі числа ILLUSTRATIVE (наближено до клінічних діапазонів
лише для правдоподібності симуляції), не валідовані.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum

from .bus import Bus, TickLoop
from .safety import SafetySupervisor
from .schemas import StimCommand

# Autonomic stimulation channels (sacral/lumbar targets). They pass through the
# SAME SafetySupervisor as locomotor channels — one safety gate for everything.
AUTONOMIC_CHANNELS = {
    "bladder": "ch_auto_detrusor",
    "bowel": "ch_auto_propulsion",
    "erectile": "ch_auto_cavernosal",
}
_AUTO_MAX_mA = 8.0      # full drive -> this amplitude (ILLUSTRATIVE, < hard limit)
_AUTO_PW_us = 200.0
_AUTO_FREQ_Hz = 30.0    # autonomic targets run at lower frequency than locomotion


class AutonomicFunction(Enum):
    BLADDER = "bladder"
    BOWEL = "bowel"
    ERECTILE = "erectile"


class AutonomicCommand(Enum):
    STORE = "store"   # continence / storage phase
    VOID = "void"     # coordinated emptying
    ENGAGE = "engage"  # erectile tumescence
    REST = "rest"


# --- ILLUSTRATIVE clinical-ish reference values (NOT validated) ---
SAFE_VOID_PRESSURE_cmH2O = 40.0   # detrusor pressure above which reflux risk rises
AD_PRESSURE_TRIGGER_cmH2O = 60.0  # bladder/bowel pressure proxy that can provoke AD
AD_BP_RISE_LIMIT = 40.0           # mmHg systolic rise flagged as dysreflexia


@dataclass
class StimDrive:
    """Coordinated autonomic stimulation request (pre-safety). 0..1 each.

    detrusor/propulsion = parasympathetic (sacral) drive that contracts the organ;
    sphincter_relax = degree the external/internal sphincter is RELAXED (synergy).
    In dyssynergia the sphincter fails to relax regardless of intent.
    """

    organ_drive: float = 0.0       # 0..1 contraction drive
    sphincter_relax: float = 0.0   # 0..1 commanded relaxation


@dataclass
class BladderModel:
    """Lower urinary tract: fill–store–void with detrusor/sphincter coupling.

    SCI default = neurogenic bladder with detrusor-sphincter dyssynergia (DSD):
    a reflex detrusor contraction is accompanied by INVOLUNTARY sphincter
    contraction, so pressure spikes and outflow is poor. Coordinated EES restores
    synergy. ILLUSTRATIVE units (mL, cmH2O).
    """

    capacity_ml: float = 450.0
    volume_ml: float = 150.0
    inflow_ml_per_s: float = 1.0        # diuresis (ILLUSTRATIVE, ~normal is slower)
    compliance: float = 12.0            # mL/cmH2O (passive wall)
    detrusor_gain_cmH2O: float = 90.0   # contraction pressure at full drive
    dyssynergia: bool = True            # SCI default; modulation can override
    reflex_threshold_ml: float = 300.0  # uninhibited reflex contraction volume
    # state
    pressure_cmH2O: float = 0.0
    sphincter_tone: float = 1.0         # 0..1 outlet resistance
    last_outflow_ml_s: float = 0.0

    def _passive_pressure(self) -> float:
        return self.volume_ml / self.compliance

    def step(self, drive: StimDrive, command: AutonomicCommand, dt: float) -> None:
        # In dyssynergia the uninhibited reflex drives the detrusor (when over-full
        # or when voiding is attempted) AND the sphincter co-contracts. With
        # restored synergy, EES reshapes the reflex: the COMMANDED drive controls
        # the detrusor and the sphincter follows the relaxation command.
        attempting = command == AutonomicCommand.VOID
        if self.dyssynergia:
            reflex = 1.0 if (self.volume_ml > self.reflex_threshold_ml or attempting) else 0.0
            detrusor = max(drive.organ_drive, 0.8 * reflex)
            self.sphincter_tone = min(1.0, 0.5 + 0.5 * detrusor)
        else:
            detrusor = drive.organ_drive
            self.sphincter_tone = max(0.05, 1.0 - drive.sphincter_relax)

        self.pressure_cmH2O = self._passive_pressure() + self.detrusor_gain_cmH2O * detrusor

        # Outflow needs detrusor pressure to exceed the outlet resistance, which a
        # co-contracting sphincter can nearly match (hence poor flow in DSD).
        outlet_resistance = self.detrusor_gain_cmH2O * self.sphincter_tone
        flow = max(0.0, 0.15 * (self.pressure_cmH2O - outlet_resistance))  # mL/s, ILLUSTRATIVE
        self.last_outflow_ml_s = flow

        inflow = self.inflow_ml_per_s if command != AutonomicCommand.VOID else 0.0
        self.volume_ml += inflow * dt - flow * dt
        self.volume_ml = max(0.0, min(self.capacity_ml, self.volume_ml))

    @property
    def fullness(self) -> float:
        return self.volume_ml / self.capacity_ml


@dataclass
class BowelModel:
    """Colon/rectum: storage + defecation reflex. Same synergy principle as the
    bladder (propulsion + anal sphincter relaxation). ILLUSTRATIVE."""

    capacity: float = 1.0
    content: float = 0.4               # 0..1 fill
    inflow_per_s: float = 0.01
    wall_tension: float = 0.0          # pressure proxy 0..1
    dyssynergia: bool = True
    sphincter_tone: float = 1.0
    evacuated: float = 0.0

    def step(self, drive: StimDrive, command: AutonomicCommand, dt: float) -> None:
        propulsion = drive.organ_drive
        if self.dyssynergia:
            self.sphincter_tone = min(1.0, 0.5 + 0.5 * propulsion)
        else:
            self.sphincter_tone = max(0.05, 1.0 - drive.sphincter_relax)
        self.wall_tension = min(1.0, self.content + 0.8 * propulsion)
        outlet = 0.5 * self.sphincter_tone + 0.1
        voiding = command == AutonomicCommand.VOID
        flow = max(0.0, self.wall_tension - outlet) * 0.4 if voiding else 0.0
        self.content += self.inflow_per_s * dt - flow * dt
        self.content = max(0.0, min(self.capacity, self.content))
        self.evacuated += flow * dt


@dataclass
class ErectileModel:
    """Cavernosal tumescence driven by parasympathetic (S2–S4) drive; sympathetic
    tone causes detumescence. Rigidity proxy 0..1. ILLUSTRATIVE."""

    pressure: float = 0.0          # 0..1 cavernosal pressure (rigidity proxy)
    para_gain: float = 1.2
    sympathetic_tone: float = 0.5  # baseline detumescence pressure
    functional_threshold: float = 0.6

    def step(self, drive: StimDrive, command: AutonomicCommand, dt: float) -> None:
        target = self.para_gain * drive.organ_drive if command == AutonomicCommand.ENGAGE else 0.0
        target = max(0.0, min(1.0, target - 0.0))
        # First-order approach toward target, with sympathetic decay at rest.
        rate = 2.0
        self.pressure += rate * (target - self.pressure) * dt
        self.pressure = max(0.0, min(1.0, self.pressure))

    @property
    def functional(self) -> bool:
        return self.pressure >= self.functional_threshold


class AutonomicDysreflexiaMonitor:
    """Life-safety: distension/noxious input below the lesion can trigger AD — a
    dangerous blood-pressure surge. Tracks a systolic-rise PROXY from organ
    pressure and flags/limits. ILLUSTRATIVE, simulation only."""

    def __init__(self, baseline_bp: float = 110.0) -> None:
        self.baseline_bp = baseline_bp
        self.bp = baseline_bp
        self.events: list[tuple[float, str]] = []

    def update(self, t: float, organ_pressure_proxy: float, dt: float) -> float:
        # BP rises when a noxious distension/pressure exceeds the AD trigger.
        drive = max(0.0, organ_pressure_proxy - AD_PRESSURE_TRIGGER_cmH2O)
        target = self.baseline_bp + 1.5 * drive
        self.bp += 3.0 * (target - self.bp) * dt
        if self.bp - self.baseline_bp > AD_BP_RISE_LIMIT:
            self.events.append((t, f"AD risk: systolic +{self.bp - self.baseline_bp:.0f} mmHg"))
        return self.bp

    @property
    def systolic_rise(self) -> float:
        return self.bp - self.baseline_bp


class AutonomicOrchestrator:
    """Maps an autonomic command into a coordinated StimDrive. With modulation
    enabled it restores detrusor/propulsion–sphincter SYNERGY; disabled, it lets
    the pathological reflex (dyssynergia) play out — the contrast we demonstrate."""

    def __init__(self, modulation: bool = True) -> None:
        self.modulation = modulation

    def drive_for(self, command: AutonomicCommand) -> StimDrive:
        if not self.modulation:
            # No coordinated stimulation: rely on the (dyssynergic) reflex.
            return StimDrive(organ_drive=0.0, sphincter_relax=0.0)
        if command == AutonomicCommand.VOID:
            # Synergic void: a MODERATE detrusor drive suffices because the
            # sphincter is genuinely relaxed -> low-pressure, complete emptying.
            return StimDrive(organ_drive=0.35, sphincter_relax=0.92)
        if command == AutonomicCommand.ENGAGE:
            return StimDrive(organ_drive=0.8, sphincter_relax=0.0)
        if command == AutonomicCommand.STORE:
            return StimDrive(organ_drive=0.0, sphincter_relax=0.0)
        return StimDrive()


@dataclass
class AutonomicRecorder:
    t: list[float] = field(default_factory=list)
    bladder_volume: list[float] = field(default_factory=list)
    bladder_pressure: list[float] = field(default_factory=list)
    outflow: list[float] = field(default_factory=list)
    bp: list[float] = field(default_factory=list)


def simulate_bladder(modulation: bool, dyssynergia: bool = True, dt: float = 0.1,
                     fill_s: float = 120.0, void_s: float = 60.0) -> tuple[BladderModel,
                                                                          AutonomicDysreflexiaMonitor,
                                                                          AutonomicRecorder]:
    """Fill the bladder, then issue a VOID command, with or without coordinated
    modulation. Returns the model, the AD monitor and a recorder."""
    bladder = BladderModel(dyssynergia=dyssynergia)
    if not dyssynergia:
        bladder.dyssynergia = False
    orch = AutonomicOrchestrator(modulation=modulation)
    ad = AutonomicDysreflexiaMonitor()
    rec = AutonomicRecorder()
    t = 0.0
    n_fill = int(fill_s / dt)
    n_void = int(void_s / dt)
    for i in range(n_fill + n_void):
        command = AutonomicCommand.STORE if i < n_fill else AutonomicCommand.VOID
        # During modulated voiding, synergy is restored (sphincter can relax).
        bladder.dyssynergia = dyssynergia and not (modulation and command == AutonomicCommand.VOID)
        drive = orch.drive_for(command)
        bladder.step(drive, command, dt)
        bp = ad.update(t, bladder.pressure_cmH2O, dt)
        rec.t.append(t)
        rec.bladder_volume.append(bladder.volume_ml)
        rec.bladder_pressure.append(bladder.pressure_cmH2O)
        rec.outflow.append(bladder.last_outflow_ml_s)
        rec.bp.append(bp)
        t += dt
    return bladder, ad, rec


# --------------------------------------------------------------------------- #
#  Bus-integrated autonomic loop — SAME Bus / TickLoop / SafetySupervisor as    #
#  the locomotor stack. One orchestration substrate and one safety gate for     #
#  BOTH locomotion and autonomic function.                                      #
# --------------------------------------------------------------------------- #

@dataclass
class AutonomicIntent:
    t: float
    function: AutonomicFunction
    command: AutonomicCommand


@dataclass
class AutonomicEvent:
    t_start: float
    function: AutonomicFunction
    command: AutonomicCommand


class AutonomicDecoder:
    """Layer-0 analogue for the autonomic loop: replays a scripted intent."""

    TOPIC = "auto_intent"

    def __init__(self, schedule: Sequence[AutonomicEvent]) -> None:
        self.schedule = sorted(schedule, key=lambda e: e.t_start)

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        ev = self.schedule[0]
        for e in self.schedule:
            if e.t_start <= t:
                ev = e
            else:
                break
        bus.publish(self.TOPIC, AutonomicIntent(t, ev.function, ev.command))


class AutonomicController:
    """Maps autonomic intent -> coordinated StimDrive -> StimCommand on the
    function's channel. The organ-drive stimulation is published for the safety
    gate; the sphincter-relaxation is carried as the coordination protocol."""

    IN = "auto_intent"
    OUT_CMD = "auto_stim_commands"
    OUT_DRIVE = "auto_drive"

    def __init__(self, modulation: bool = True) -> None:
        self.orch = AutonomicOrchestrator(modulation=modulation)

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        intent: AutonomicIntent | None = bus.latest(self.IN)
        if intent is None:
            return
        drive = self.orch.drive_for(intent.command)
        ch = AUTONOMIC_CHANNELS[intent.function.value]
        cmd = StimCommand(t=t, channel_id=ch, amplitude_mA=drive.organ_drive * _AUTO_MAX_mA,
                          pulse_width_us=_AUTO_PW_us, frequency_Hz=_AUTO_FREQ_Hz)
        bus.publish(self.OUT_CMD, [cmd])
        bus.publish(self.OUT_DRIVE, (intent, drive))


class AutonomicCord:
    """Runs autonomic StimCommands through the SHARED SafetySupervisor, recovers
    the (possibly clamped) organ drive, steps the organ models, and feeds organ
    pressure into the supervisor's autonomic-dysreflexia watchdog."""

    IN_CMD = "auto_stim_commands"
    IN_DRIVE = "auto_drive"
    OUT = "auto_state"

    def __init__(self, safety: SafetySupervisor, modulation: bool = True,
                 dyssynergia: bool = True) -> None:
        self.safety = safety
        self.modulation = modulation
        self.base_dyssynergia = dyssynergia
        self.bladder = BladderModel(dyssynergia=dyssynergia)
        self.bowel = BowelModel(dyssynergia=dyssynergia)
        self.erectile = ErectileModel()

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        cmds = bus.latest(self.IN_CMD) or []
        payload = bus.latest(self.IN_DRIVE)
        if payload is None:
            return
        intent, drive = payload
        approved_drive = 0.0
        for cmd in cmds:
            verdict = self.safety.check(cmd)
            if verdict.approved:
                approved_drive = verdict.command.amplitude_mA / _AUTO_MAX_mA
        eff = StimDrive(organ_drive=approved_drive, sphincter_relax=drive.sphincter_relax)

        if intent.function == AutonomicFunction.BLADDER:
            voiding = intent.command == AutonomicCommand.VOID
            self.bladder.dyssynergia = self.base_dyssynergia and not (self.modulation and voiding)
            self.bladder.step(eff, intent.command, dt)
            self.safety.update_autonomic_dysreflexia(self.bladder.pressure_cmH2O,
                                                     AD_PRESSURE_TRIGGER_cmH2O)
            bus.publish(self.OUT, {"function": "bladder", "volume": self.bladder.volume_ml,
                                   "pressure": self.bladder.pressure_cmH2O,
                                   "ad_risk": self.safety.autonomic_ad_risk})
        elif intent.function == AutonomicFunction.BOWEL:
            self.bowel.dyssynergia = self.base_dyssynergia and not self.modulation
            self.bowel.step(eff, intent.command, dt)
            bus.publish(self.OUT, {"function": "bowel", "content": self.bowel.content})
        elif intent.function == AutonomicFunction.ERECTILE:
            self.erectile.step(eff, intent.command, dt)
            bus.publish(self.OUT, {"function": "erectile", "rigidity": self.erectile.pressure})


@dataclass
class IntegratedAutonomicSystem:
    loop: TickLoop
    bus: Bus
    safety: SafetySupervisor
    decoder: AutonomicDecoder
    controller: AutonomicController
    cord: AutonomicCord
    log: list = field(default_factory=list)

    def run(self, duration_s: float) -> list:
        n = int(round(duration_s / self.loop.dt))
        for _ in range(n):
            self.loop.step()
            self.log.append(self.bus.latest("auto_state"))
        return self.log


class BladderManager:
    """Closed-loop bladder management — the clinical control concept.

    Замкнутий контролер міхура з СЕНСОРОМ НАПОВНЕННЯ. Замість скриптованого
    спорожнення він сам вирішує, КОЛИ спорожняти, за трьома тригерами:
      * за обʼємом (досягнуто порогу),
      * за розкладом (timed voiding, як у клінічній практиці),
      * ПРОАКТИВНО за тиском — спорожнити ДО входу в небезпечну зону автономної
        дисрефлексії (профілактика загрозливого стану).
    Між спорожненнями тримає фазу зберігання; під час void — координовану EES.
    """

    OUT = "auto_intent"

    def __init__(self, void_threshold_ml: float = 250.0, residual_target_ml: float = 25.0,
                 schedule_interval_s: float | None = None,
                 ad_guard_pressure_cmH2O: float = 50.0, void_timeout_s: float = 60.0) -> None:
        self.void_threshold_ml = void_threshold_ml
        self.residual_target_ml = residual_target_ml
        self.schedule_interval_s = schedule_interval_s
        self.ad_guard_pressure = ad_guard_pressure_cmH2O
        self.void_timeout_s = void_timeout_s
        self.phase = AutonomicCommand.STORE
        self._last_void_end = 0.0
        self._void_start = 0.0
        self.void_count = 0
        self.proactive_voids = 0

    def tick(self, t: float, dt: float, bus: Bus) -> None:
        st = bus.latest("auto_state")
        vol = st["volume"] if st and st.get("function") == "bladder" else 0.0
        press = st["pressure"] if st and st.get("function") == "bladder" else 0.0

        if self.phase == AutonomicCommand.STORE:
            by_volume = vol >= self.void_threshold_ml
            by_schedule = (self.schedule_interval_s is not None
                           and t - self._last_void_end >= self.schedule_interval_s)
            by_ad_guard = press >= self.ad_guard_pressure  # proactive AD prevention
            if by_volume or by_schedule or by_ad_guard:
                self.phase = AutonomicCommand.VOID
                self._void_start = t
                self.void_count += 1
                if by_ad_guard and not by_volume:
                    self.proactive_voids += 1
        else:  # VOIDING
            if vol <= self.residual_target_ml or (t - self._void_start) > self.void_timeout_s:
                self.phase = AutonomicCommand.STORE
                self._last_void_end = t

        bus.publish(self.OUT, AutonomicIntent(t, AutonomicFunction.BLADDER, self.phase))


def build_managed_bladder_system(modulation: bool = True, dyssynergia: bool = True,
                                 dt: float = 0.1, void_threshold_ml: float = 250.0,
                                 schedule_interval_s: float | None = None,
                                 safety: SafetySupervisor | None = None
                                 ) -> IntegratedAutonomicSystem:
    """Closed-loop managed bladder on the shared Bus/TickLoop/SafetySupervisor.
    A BladderManager replaces the scripted decoder and drives voiding from the
    sensed fill state."""
    bus = Bus()
    loop = TickLoop(dt=dt, bus=bus)
    safety = safety or SafetySupervisor()
    manager = BladderManager(void_threshold_ml=void_threshold_ml,
                             schedule_interval_s=schedule_interval_s)
    controller = AutonomicController(modulation=modulation)
    cord = AutonomicCord(safety, modulation=modulation, dyssynergia=dyssynergia)
    for c in (manager, controller, cord):
        loop.add(c)
    sysm = IntegratedAutonomicSystem(loop, bus, safety, manager, controller, cord)
    sysm.manager = manager
    return sysm


def build_autonomic_system(schedule: Sequence[AutonomicEvent], modulation: bool = True,
                           dyssynergia: bool = True, dt: float = 0.1,
                           safety: SafetySupervisor | None = None,
                           bus: Bus | None = None,
                           loop: TickLoop | None = None) -> IntegratedAutonomicSystem:
    """Assemble the autonomic loop on the SAME Bus/TickLoop/SafetySupervisor as
    the locomotor stack. Pass an existing ``bus``/``loop``/``safety`` to literally
    share one substrate and one safety gate with locomotion."""
    if bus is None:
        bus = Bus()
    if loop is None:
        loop = TickLoop(dt=dt, bus=bus)
    safety = safety or SafetySupervisor()
    decoder = AutonomicDecoder(schedule)
    controller = AutonomicController(modulation=modulation)
    cord = AutonomicCord(safety, modulation=modulation, dyssynergia=dyssynergia)
    for c in (decoder, controller, cord):
        loop.add(c)
    return IntegratedAutonomicSystem(loop, bus, safety, decoder, controller, cord)
