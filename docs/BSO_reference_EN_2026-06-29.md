# BSO — Program Reference Sheet

**Brain-Spine Orchestrator (BSO)** — a brain ↔ spinal-cord orchestrator
**For:** Igor Sharanda · **Date:** 2026-06-29 · **Type:** working simulator (digital twin), not slides

---

## What it is, in one sentence

A "conductor" program that sits **between a movement-intent decoder in the brain and a spinal stimulator**. A person thinks "step" — the program translates that into coordinated electrical stimulation of dozens of muscles in real time, adapts to feedback from the body, and stays inside hard safety limits. Today it runs on a **virtual twin of the body**; tomorrow the same code plugs into a real stimulator.

> The program is already built around **your real setup**: your electrode array (5-6-5 paddle, 16 contacts) and **your actual stimulation programs** from a clinical partner. It is not an abstraction — it is about your body.

---

## Program sections

### 1. Intent decoder (Layer 0)
**Purpose:** the source of the command "I want to stand / take a step."
**What it does:** turns intent (from the brain, or — in the no-chip variant — from spared residual body signals) into a clean digital intent signal.
**How it helps:** this is the "gas pedal" — control is always yours; the program only executes your will, it never decides for you.
*Modules: decoder_stub, intent (residual-signal decoding — the no-brain-chip path), fusion (merging several weak signals into one intent).*

### 2. Conductor / gait generator (Layer 1)
**Purpose:** turn a simple "walk" intent into the correct walking rhythm.
**What it does:** keeps the phase clock of the step (stance/swing, left/right) and breaks intent into targets for each muscle group. This is a model of the spinal "gait rhythm generator" (CPG), like in a healthy spinal cord.
**How it helps:** you don't consciously control every muscle — you think "walk," and the program generates the rhythm itself.
*Modules: orchestrator, rl_gait (cross-speed gait learned via evolution methods), distill (compressing the "ideal" offline gait into a fast real-time one).*

### 3. Effectors — translation into stimulation (Layer 2)
**Purpose:** turn "this muscle needs this much drive" into concrete electrical pulses on concrete contacts.
**What it does:** for each muscle group it computes which electrode contact to fire, at what amplitude/frequency/pulse width.
**How it helps:** this is the bridge from intent to the real stimulator — it speaks the language of your electrode array.
*Modules: effectors, muscle (Hill muscle model: activation → force), electrode_array (your 5-6-5 paddle), stim_programs (your real stimulator programs), stim_planner / program_mapping / mapping (the program LEARNS the clinician's pattern and automates contact selection that is done by hand today).*

### 4. Feedback — eyes and balance (Layer 3)
**Purpose:** see what the body is actually doing and correct on the fly.
**What it does:** from sensors (joint angles, foot loading, acceleration, muscle activity) it estimates step phase and balance, catches errors (foot drag, asymmetry, loss of balance) and feeds corrections back to the conductor.
**How it helps:** a closed loop — the program doesn't "fire blind," it constantly corrects the step the way a healthy nervous system does.
*Modules: feedback, sensors (modeling sensor noise/dropout for robustness).*

### 5. Adaptation and learning (Layer 4)
**Purpose:** adjust to fatigue, to "your day," to parameter drift.
**What it does:** between steps and sessions it slowly recalibrates stimulation, learns to compensate for muscle fatigue, and tunes optimal settings mathematically rather than by guessing.
**How it helps:** the system isn't "frozen" — it improves over time and doesn't need constant manual retuning.
*Modules: adaptation, learned_adaptation (a small learned compensation policy), bopt (Bayesian optimization — smart auto-tuning), degradation (a fatigue/drift model to train against).*

### 6. Safety — supervisor with veto power (Layer 5)
**Purpose:** no command may cause harm.
**What it does:** EVERY stimulation command passes through this layer. It clamps or blocks anything outside safe limits, runs a "guardian" against autonomic dysreflexia (a dangerous blood-pressure spike — critical precisely at thoracic level), and has an emergency stop.
**How it helps:** this is your safety harness — no other module can bypass it. Fully covered by tests.
*Modules: safety, ad_guardian (dysreflexia prediction), config/limits (hard constant limits).*

### 7. Digital twin of the body (biomechanics)
**Purpose:** safely test everything on a virtual body before touching the real one.
**What it does:** simulates the lower limbs on real physics — from simple kinematics to full dynamics (MuJoCo) and a scientifically validated musculoskeletal model (OpenSim).
**How it helps:** thousands of experiments with zero risk to you — this is where we "invent" and validate ideas.
*Modules: biomech (base / kinematic / mujoco / opensim), neurostim_gym (an open benchmark arena for reproducible testing).*

### 8. Autonomic functions — critical at thoracic level
**Purpose:** with a Th5-Th6 injury these matter no less than legs — bladder, bowel, blood pressure, erectile function.
**What it does:** a dedicated neuromodulation module for these functions + a clinical protocol + scheduled "reflex discipline" + a clinician-grade urodynamic study from the bladder model.
**How it helps:** a real gain in quality and safety of life right now — this is the nearest evidence-backed target for thoracic level.
*Modules: autonomic, autonomic_clinical, autonomic_training, urodynamics.*

### 9. Recovery and neuroplasticity
**Purpose:** the main bet is not "walk with stimulation" but to **heal** and regrow connections.
**What it does:** makes RECOVERY (plasticity) the control objective, not just function here-and-now; runs the rehab program as a single source of truth with a tracker.
**How it helps:** a path toward needing stimulation less over time — like patients who showed recovery even with the bridge switched off.
*Modules: plasticity, recovery, recovery_optimizer.*

### 10. Cohort — each patient speeds up the next
**Purpose:** not to start from scratch each time.
**What it does:** a meta-learned "prior" from many patients' experience gives a fast personalization start for a new one.
**How it helps:** a unique edge for Ukraine / 1TMO here — a large SCI cohort as a world-class dataset to train the adaptive layer.
*Modules: cohort, cohort_model.*

### 11. Clinical layer + AI advisor (outside real time)
**Purpose:** keep the clinician in the loop and explain decisions in human language.
**What it does:** a human-in-the-loop approves settings; clinical reports are generated (UA+EN); an AI advisor turns the data stream into recommendations; an in-dashboard AI assistant answers questions on your real data.
**How it helps:** transparency and trust — every decision can be shown and explained to a doctor.
*Modules: clinical_approval, clinical_mapping, clinical_report, advisor, supervisor_llm, dashboard_agent.*

### 12. Framework and bridge to reality
**Purpose:** stitch all layers into one living loop and prepare for connecting real hardware.
**What it does:** a deterministic tick loop runs the whole circuit; telemetry is the seam where a real stimulation platform plugs in tomorrow; visualization shows the gait and the graphs.
**How it helps:** it proves this is a system, not a demo — and that the transition to real hardware is already designed in.
*Modules: bus, schemas, runtime, unified, api_schema, telemetry, viz/dashboard, web.*

---

## Under the hood — in plain words for a CTO

If someone asks "is this just pictures?" — here is the honest answer in five points:

1. **This is a working program, not a presentation.** ~50 Python modules, ~33 automated test files (pytest). Everything runs and executes.

2. **The heart is a real-time closed loop.** On every "tick" the signal runs around the loop: intent → gait conductor → effectors → **safety check** → digital body → sensors → back for correction. This is control-systems engineering architecture — the same logic used in robotics and avionics.

3. **The body runs on real physics.** Motion is tested not with "animation" but on industrial scientific engines: **MuJoCo** (dynamics) and **OpenSim** (a scientist-validated musculoskeletal model) + a Hill muscle model. These are the tools biomechanics labs worldwide use.

4. **There is machine learning inside — but in the right place.** Bayesian optimization auto-tunes stimulation parameters, an evolution method trains gait across speeds, meta-learning transfers experience between patients. Yet **no LLM sits in the motor loop** — the "language model" works only at the level of reports and recommendations, never controlling stimulation directly. Real movement is deterministic code and controllers.

5. **Safety is built in, not bolted on.** A separate supervisor with **absolute veto power** checks every command; no module can bypass it; it is fully covered by tests.

**A clear "real vs mocked" line.** Honestly: the intent decoder and the patient himself are mocked for now (simulation). But the program is already built around the **real** — your electrode array and your clinical stimulation programs. And "telemetry" is a pre-designed connector where a real stimulation platform (ONWARD/NeuroRestore class) plugs in. So our layer **sits on top of** real hardware rather than duplicating it.

**One sentence to close the question:**
"This is an orchestration layer — a software bridge between a brain decoder and a spinal stimulator. It translates the intent to 'walk' into coordinated stimulation of dozens of muscles in real time, learns, adapts, and stays within safety limits. Today it is proven on a real-physics digital twin of the body; tomorrow the same code plugs into a real stimulator through the telemetry layer."
