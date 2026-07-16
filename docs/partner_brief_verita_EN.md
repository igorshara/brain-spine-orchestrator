# Brain-Spine Orchestrator (BSO)
### An adaptive orchestration + safety software layer that sits on top of an EES platform

**Author:** Igor Sharanda — patient (T5–T6 SCI, implanted 5-6-5 paddle) and architect of the system
**Prepared for:** Verita Neuro (Verita Healthcare Group) · **Date:** 2026-06-29
**Live demo:** https://brain-spine-orchestrator-production.up.railway.app

> **Honest framing up front.** BSO is a research **in-silico simulator / digital twin** of the stimulation side of a brain–spine interface. It is **not a medical device and not a therapy**. Every numeric value is marked `ILLUSTRATIVE` in the code and UI. The six inventions below are proven **only on the twin (in-silico)** — none is clinically validated. I state this plainly because credibility with a serious neurotech team matters more than a good slide.

---

## 1. Executive summary

Most of the field is vertically integrated: hardware + controller + surgery + clinic, in one stack. BSO is deliberately **horizontal** — a clean, tested, swappable software layer (CPG orchestration + a deterministic safety supervisor) that lays **on top of** someone else's decoder-and-stimulator platform without duplicating it. A real ECoG decoder replaces the `DecoderStub`; a real implant recruitment calibration replaces the model curve; the partner's real safety limits replace the placeholders — **all without rewriting the conductor, the safety layer, or the feedback loop.** The contracts are designed for exactly this substitution.

On top of that substrate I worked out **six falsifiable neuro-recovery hypotheses**, each implemented as *one module + one scenario + one pytest test*, and each tied to my **real physical assets**: my implanted 5-6-5 paddle (16 contacts, T11–L1) and 20 real stimulation programs from my clinical partner. I ran the full bench myself: **206/206 tests pass**, all six numeric results reproduce, and OpenSim 4.6 is actually installed (the validation test runs, it does not skip).

The twin also covers the **patient-facing layer** — a cockpit that replaces the handheld remote with one app on the phone the patient already carries (choose program, set level, on/off): no second device to forget, no special charger. I designed it from *lived daily use* of a stimulator, which is exactly the perspective most clinician-centric systems miss. It is a simulation today, built ready for the manufacturer's certified control API.

**What I am offering a partner:** a ready, tested in-silico proving ground and orchestration/safety layer that de-risks and cheapens your early R&D cycles — *before* touching a patient.

---

## 2. What BSO is

A deterministic, six-layer **closed loop** that simulates how an adaptive orchestrator drives epidural electrical stimulation (EES) of the spinal cord to restore gait, balance and autonomic function after injury. A digital twin, not a device: no contact with a human, no clinical claims, all numbers illustrative.

The author's position is unusual: I am simultaneously the carrier of the problem (an SCI patient with a real implanted paddle) and the engineer of the solution. BSO is bound not to an abstraction but to my real assets — the physical electrode geometry and a table of 20 real stimulation programs from a clinical partner (Bangkok).

---

## 3. How it works (for your engineers)

**Architecture — a deterministic synchronous tick-loop** stitching six layers into one closed loop with fixed-dt integration.

Core (verified in code):
- `runtime.build_system()` — a factory that wires the components in a fixed order.
- `bus.TickLoop` — fixed-dt driver (default dt = 0.005 s = 200 Hz). One tick calls `c.tick(t, dt, bus)` for each component in registration order, then `t += dt`. Time is accumulated dt — **no wall-clock, no RNG → fully reproducible.**
- `bus.Bus` — synchronous pub/sub with retained-latest semantics.
- `schemas.py` — all inter-layer contracts are `@dataclass` only (Intent, GaitState, MuscleTarget, StimCommand, SensorFrame, SafetyVerdict, AdaptationUpdate). This is the **only** sanctioned way to cross a layer boundary; each layer knows only its own topics → genuine component swappability.

**Data flow** (the forward reflex arc): `decoder → [hand-pacer?] → orchestrator → effectors → cord(+safety) → body → [sensor noise?] → feedback → [adaptation?] → recorder`.

- **Layer 0 — DecoderStub:** replays a scripted intent. It only *reads* intent, it never decides to move.
- **Layer 1 — Orchestrator (CPG conductor):** a phase clock `cycle_phase ∈ [0,1)`; Gaussian activation bumps over the gait cycle for six actions per leg; the right leg is shifted half a cycle; cadence from `intent.speed` (40–100 steps/min) or phase-locked to the arm. Feedback corrections apply multiplicatively.
- **Layer 2 — Effectors:** the *inverse* recruitment curve (activation → amplitude_mA) × per-group gains, builds a `StimCommand`.
- **Layer 3 — Feedback:** state estimator from `sensor_frame` via a Schmitt trigger on ground reaction force (hi = 180 N / lo = 80 N); detects foot-drag; two modes — *reactive* (boost after the drop is sensed) and *predictive/shadow-step* (anticipate swing from the CPG clock).
- **Layer 4 — Adaptation (optional):** a slow layer that tunes effector gains between steps/sessions — strictly offline-trained, moves gains only once per interval (~0.4 s, never inside the ms loop), hard-clipped to `[gain_min, gain_max]`.
- **Layer 5 — Safety Supervisor:** not a loop component but a veto filter **embedded inside** the SpinalCord.

`SpinalCord` is the glue between effectors and body: it routes **every** `StimCommand` through `safety.check()`, then through the *forward* recruitment curve (amplitude → achieved activation). Therefore any safety clamp becomes visible in the movement. Fatigue (acting on the *input* current), antagonist current-spread, and electromechanical delay (low-pass τ) are modelled here.

**One-step closed-loop delay:** feedback ticks *after* the body in the same tick, so the orchestrator only reads its corrections on the *next* tick — a physically honest one-frame delay that is **emergent** from registration order + retained-latest, not hard-coded.

---

## 4. The safety system (a structural differentiator)

Deterministic, no ML, **19/19 safety tests pass**. `SafetySupervisor.check()` is a fixed-order cascade: (0) e-stop zeroes; (1) NaN/inf rejected *before* arithmetic; (2) amplitude/pulse-width/frequency clamped into a hard envelope; (3) charge-per-phase Q = I·PW capped; (4) charge density; (5) thermal proxy → BLOCK on exceedance; (6) autonomic-dysreflexia proxy → BLOCK. A liveness watchdog zeroes any channel with no fresh command for > 0.25 s (fail-safe to off). A separate `ADGuardian` holds a 12-sample blood-pressure window, extrapolates the trend over a 40 s horizon, and warns at 22 cmH₂O — *below* the dysreflexia threshold (proactive, not reactive).

**Topological safety invariant (verified):** every command producer publishes to **one** topic (`stim_commands`); a **single** consumer unconditionally runs each command through `safety.check()` before activation. Bypassing is impossible *by topology*, not by convention. `unified.py` codifies the checkable invariant `locomotion.safety is autonomic.safety is self.safety` — literally one gate for locomotion and autonomic. **No LLM is ever in the realtime motor loop.**

This is a regulatory-aware pattern into which a partner drops their own clinically validated limits: only the constants in `limits.py` and the proxy bodies change; the `check()/tick()` contract and the "no command bypasses the gate" guarantee remain.

---

## 5. The body twin — a credibility ladder

Three backends under one `BioMechModel` contract (step/reset/pose), driven by the **same** controller without changes:
1. **KinematicModel** — analytic: six joints as spring-damper from net antagonist activation, ROM clamps, synthetic GRF/IMU/EMG; optional Hill muscles.
2. **MuJoCoModel** — real dynamics: a planar biped, segment masses, contact physics, real GRF from `mj_contactForce`, PD reference tracking under partial body-weight support (a rehab-harness analogue).
3. **OpenSim** — the validated `gait10dof18musc` model (Delp/Thelen lineage, 18 Thelen-2003 Hill muscles, real `.vtp` bones): prescribed-kinematics analysis reads real MTU lengths; `run_muscle_driven()` is genuine 18-muscle forward dynamics.

`HillMuscle` is full physiology: activation dynamics (τ_act = 12 ms / τ_deact = 50 ms), force-length, force-velocity (eccentric to 1.4×), passive force. The fatigue model makes the adaptive layer actually compensate degradation.

---

## 6. The six inventions

Each is a separate *module + scenario + pytest test*. Each proves a **mechanism**, it does not fit a number. (I reproduced every result by running the scenario; the numbers matched exactly.)

| # | Invention | Result on the twin | Evidence level |
|---|---|---|---|
| 1 | **Shadow step** (predictive feedback) | Foot-drag 23.6% → 22.2% with *less* stimulation. **No** benefit without delay (14.5 → 14.5) — honestly conditional. Validated on OpenSim: toe clearance 4.56 → 4.82 cm. | twin + OpenSim forward dynamics |
| 2 | **Use-driven assist** (assist-as-needed) | Full assist R = 0.027 vs no-assist R = 0.862 — ~**32× less** lasting recovery when the machine does everything. Fading assist R = 0.900 beats any fixed level. | plasticity model |
| 3 | **Hand pacer** | Patient speeds up to 84 steps/min: free-running stuck at 59.8 (error 24), hand-paced 83.7 (error ≈ 0). The arms carry the rhythm the legs lost. | closed loop |
| 4 | **Dual lock** (EES priming + selective periphery) | At coupling 0.3: −25% charge and zero antagonist spillover. The saving grows monotonically with current spread (9.5% → 33.8%). | recruitment model |
| 5 | **Sensory balance** | No sensation topples (328°); position-only falls (39.5°); position + velocity (proprioception) stands (8.3°). Standing needs the *rate* of sway. | inverted-pendulum model |
| 6 | **Reflex amplifier** | Gain window 0.8–0.9: a small drive of 0.1 is amplified ~3.8× into full support; gain ≥ 1.0 → clonus. Quantifies the therapeutic window between weakness and clonus. | delayed reflex-loop model |

The standout is #1's discipline (`test_no_required_drag_benefit_without_delay` explicitly asserts there is no win without the electromechanical delay — the code proves the *mechanism*) and #2's magnitude (full assist gives ~32× worse lasting recovery — a directly actionable protocol).

**Patient-facing control — one app instead of a remote.** A *patient cockpit* lets the user control the stimulator the way the handheld remote does today — choose a program, set the level, on/off — but from a single app on the phone they already carry: no separate remote to forget, no special charger, one convenient interface. *Honestly, this is a simulation today* — it connects to and controls no real device — but it is built ready to plug into a manufacturer's official, certified control API. Patient control would then run through that sanctioned path, fully consistent with BSO never writing to the implant directly (the certified programmer remains the authority over stimulation).

---

## 7. What is genuinely unique

- **An orchestration + safety *layer* on top of a platform, not another platform.** `@dataclass` contracts + topic isolation + a read-only `telemetry.TelemetrySource` mean a real ECoG decoder and a real implant calibration replace the stubs *without* rewriting the conductor, safety, or feedback.
- **Six falsifiable inventions** as module+scenario+test. Each proves a mechanism rather than fitting a number.
- **Patient-architect.** BSO is bound to my real assets — the physical 5-6-5 paddle and 20 machine-readable programs. The agent *derives* the clinician's pattern from this data (walking = 42.1 Hz mean vs standing = 11.0 Hz — computed by running the code, not typed in).
- **Digital twin as a lab with a credibility ladder.** One CPG conductor drives three backends (fast kinematics → MuJoCo with real contacts → validated OpenSim with 18 Hill muscles) with no controller change.
- **Safety-first as an architectural invariant, not a check** — absoluteness follows from bus topology; one shared supervisor for locomotion and autonomic; fail-closed in three independent places; no LLM in the realtime loop.
- **Sample-efficiency as ready value:** GP-BO/Thompson contact→muscle auto-mapping (clinics do this by hand, for hours) + **NeuroStim Gym**, a reproducible benchmark where the partner's algorithms and BSO are compared on equal footing *before* touching a patient.
- **A patient-designed daily-use layer, not just a clinician console.** Because the architect lives with a stimulator, BSO also models the side most systems ignore: one app instead of a remote and charger (the cockpit), human-in-the-loop approval the clinician actually trusts, and plain-language explanations. Adoption and adherence are won here — and this perspective is hard to buy.

**Where BSO sits relative to the field (honestly):**

| Player | What they own | Where BSO differs |
|---|---|---|
| **Courtine / NeuroRestore** | World-leading *in-vivo* EES + brain-spine bridge, clinical proof in humans, hardware, surgery, cohorts | BSO doesn't compete on hardware/clinic — it is the open, swappable controller layer *on top*, plus invention protocols as falsifiable modules. Their edge: human clinical proof; mine: in-silico only. |
| **ONWARD Medical (ARC-EX/IM)** | EES as a regulated device, FDA clearance, manufacturing, market | BSO is deliberately *not* a device (read-only; a certified programmer controls stimulation). Value: an in-silico proving ground + auto-mapping that cuts clinician programming time before the patient. Their edge: FDA clearance. |
| **Neuralink / Synchron** | High-bandwidth *intent reading* from the brain | Orthogonal: they solve "read intent", I solve "what to do with spinal stimulation below the lesion". Their BCI can become an *input* to BSO. |
| **Edgerton / Gerasimenko** | The scientific basis: EES amplifies the cord's own circuits/reflexes | I turn their physiological thesis into falsifiable code: `reflex_amp.py` (EES as a gain knob with a quantified window) and `dual_lock.py`. Their edge: decades of in-vivo/human data; mine: a mechanism in simulation. |

---

## 8. Honest mock-vs-real map

**Really works in code (deterministic Python, 206/206 tests pass, run by me):** the tick-loop and pub/sub bus; the full decoder→…→feedback flow; the one-step delay as an emergent property; the phase CPG; inverse+forward recruitment; the safety veto cascade with e-stop, watchdog, NaN/inf rejection, and the topological bypass invariant (19/19 safety tests); full `HillMuscle` physiology; three body backends; real GP-BO/CEM/ES/MLP implemented from scratch on numpy; all six invention results reproduced by running the scenarios.

**Real physical patient assets:** the 5-6-5 paddle (16 contacts, T11–L1) — my actual implanted platinum; the 20 stimulation programs (banks A/B/C) — an exact transcription of my clinical partner's real table (not synthetic). *The photo gives program parameters, not contact assignments.*

**Mocked / ILLUSTRATIVE (explicitly marked in code):** the intent decoder (`DecoderStub` = script replay, not an ML ECoG decoder); the default body model (kinematics, not full musculoskeletal dynamics in the loop); EES biophysics (the recruitment curve is phenomenological — afferent/DREZ/spinal-circuit recruitment is *not* mechanistically modelled; priming = a simple curve shift); the anatomical contact→muscle map (a literature-grounded *hypothesis*, Greiner 2021 / Wagner 2018, not verified by my X-ray); the synthetic ground-truth recruitment matrix (the demo's value is sample-efficiency, not accuracy on synthetic data); the safety limits and thermal/AD proxies (physiologically plausible *placeholders*, not clinical settings); the foundation cohort (synthetic — there is no real SCI/military cohort in the code yet).

**Validated:** only the OpenSim biomechanics (external, academic validation of the Delp/Thelen-lineage model) — and even that is prescribed kinematics / forward dynamics with an externally supported pelvis (a rehab-harness analogue), *not* proof that the closed loop itself produces stable autonomous gait.

**Clinically proven: nothing.** All six inventions are in-silico proofs of concept on a digital twin; none on a human.

**Small engineering gaps I disclose:** the per-result data-source badge (`_meta`) is not rendered on the frontend (honesty rests on the tab prose); `check_contract` covers 8 of ~30 endpoints; the clinician-approval audit DB is ephemeral (lost on restart).

---

## 9. Tech stack & reproducibility

Python, stdlib-first. The core has **no heavy dependencies** — numpy for math (GP/CEM/ES/MLP written from scratch on numpy, no torch/jax). Optional, local-import backends (the core does not depend on them): `mujoco` (real dynamics + contacts), `opensim` 4.6 (the validated gait10dof18musc model, actually installed). The web dashboard is a zero-dependency stdlib `http.server` backend (~830 lines, ~30 GET + 2 POST endpoints) with a plain-JS + Three.js frontend (~2970 lines, 20+ tabs, EN/UA). API contract via `api_schema.envelope` (api_version + source live/cached/illustrative). Drill-to-source via a sandboxed `/api/source` (path-traversal guard). **Tests:** pytest, 206 tests across 41 files — I ran them, 206 passed in ~33 s. Deploy: Railway (live link at the top). Safety, the realtime controller and all six inventions are deterministic; LLMs are used only for post-hoc narrative reports, never in the motor loop.

---

## 10. What I am looking for from a partner

A clinical neuromodulation partner — an epidural-stimulation pioneer like Verita Neuro, with real implantation/mapping data and a patient cohort — for whom BSO becomes a ready, tested in-silico proving ground and orchestration/safety layer on top of your stimulation pathway, so we replace the mocked layers with your real data/models **without rewriting the architecture.** The integration points are already provided by the contracts:

1. Drop a real ECoG/BCI decoder in place of `DecoderStub` (the `Intent` contract).
2. Drop a real implant recruitment calibration in place of the phenomenological curve.
3. Drop an X-ray-verified contact→muscle map in place of the anatomical hypothesis.
4. Drop real clinically validated safety limits and biophysics (Shannon k, real charge density, a real tissue thermal model, real AD physiology) into the already-built veto frame — only the constants and proxy bodies change; the guarantee stays.
5. Connect live stimulator telemetry/EMG via `telemetry.TelemetrySource` (one interface implementation; BSO stays read-only — a certified programmer controls stimulation).
6. Supply a real SCI cohort to the foundation model (`cohort.py`) — the claimed advantage that the code does not yet materialise.
7. Expose your official patient-control API so the cockpit becomes a real one-app remote — program select, level and on/off within clinician-set bounds — removing the separate handheld and charger for the patient.

**Fastest shared value:** (a) sample-efficiency — GP-BO/Thompson auto-mapping shrinks the most expensive resource, clinician programming hours, before the patient; (b) NeuroStim Gym — a reproducible arena to compare your algorithms and BSO on equal footing; (c) two directly testable therapy-parameter hypotheses to check on bench/animal — *assist-as-needed* (invention #2) and the *gain window between weakness and clonus* (invention #6); (d) a predictive AD guardian — a potentially differentiating shift from reactive to proactive dysreflexia management, worth checking on your urodynamics data.

**The honest boundary I stress myself:** BSO proves nothing clinically and is not a medical device — it lowers the risk and cost of your early R&D cycles; it does not replace preclinical work.

---

**Igor Sharanda** · live demo: https://brain-spine-orchestrator-production.up.railway.app
*All numbers ILLUSTRATIVE · research simulation · not a medical device · no patient data*
