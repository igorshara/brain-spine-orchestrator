# Brain-Spine Orchestrator (BSO): partner brief

> **A research simulator. It is not a medical device, not firmware and not a therapy.** It has
> no connection to any real stimulator, implant or telemetry. Every simulated number is
> ILLUSTRATIVE and not clinically validated. The stimulation programs shown are the author's
> own, published by him. They cover no other person.
>
> Author: Ihor Sharanda, who lives with a spinal cord injury and a Medtronic implanted
> stimulator.

## 1. The problem, from one user

Two failures of ordinary daily use, in the author's own report:

- He forgot his remote and waited five to six days for it.
- He forgot to switch the stimulator off. It ran for a long time, and he then had strong
  spasms. The link between the long run and the spasms is his own report and has not been
  measured.

Neither failure is about therapy. Both are about the patient-side controller.

## 2. What the demonstrator shows

Four screens, all simulated:

| Screen | What a viewer does | What it shows |
|---|---|---|
| Overview | Reads the two cases, chooses one to play | The problem and the concept in one view |
| Controller | Plays lost reply, lost command, refusal and forgotten remote | The controller and the implant can disagree. Connection loss is shown as Unknown, never as Off. A pre-authorized backup can only switch off |
| Session | Starts a reminder, ignores it, loses the connection | A reminder asks, asks again, then tells a trusted person. It measures time since the reminder started, not stimulation time |
| Research | Inspects the simulator's charts and walking model | The evidence and its limits, including negative results |

Everything is a concept for discussion. None of it is a feature of any existing system, and
none of it asks for access to one.

## 3. Under the demonstrator

```
Decoder(0) → CPG orchestrator(1) → Effectors(2) → [Safety supervisor(5): veto]
   ↑                                                         ↓
Feedback(3) ← sensor corruption ← Body (kinematic, MuJoCo or OpenSim) ← spinal cord model
   ↑
Adaptation(4)                                  + autonomic layer (bladder, bowel, erectile)
```

- A deterministic safety supervisor checks every stimulating command. Switch-off delivers no
  stimulation, so it is never vetoed.
- No language model runs in the motor loop.
- The body is swappable: kinematic, planar MuJoCo, or the published OpenSim
  `gait10dof18musc` model. Validation of that model belongs to its authors, not to BSO.

## 4. Measured in simulation

Every value was reproduced on 2026-11-02. Sources and references are in `validation.md`.

| Capability | Result |
|---|---|
| Walking, kinematic body | 76 steps/min, balance 1.00, 0 safety events |
| Walking, MuJoCo body | pelvis 0.89 m, trunk lean 6.8° (95th percentile), peak force 496 N at ~490 N body weight, stance alternation −0.97, 0 safety events |
| Trunk push | 15.0° peak with active balance, 41.3° passive |
| Foot clearance under degradation, kinematic | 100% nominal, 27% degraded, 92% with adaptation |
| Foot clearance under fatigue, MuJoCo | 99% nominal, 69% fatigue, 98% with adaptation, 98% with noise added |
| Bladder model | dyssynergia 94 cmH₂O, 184 mL residual, +41 mmHg; coordinated 54 cmH₂O, 0 mL, +0 mmHg |
| Dysreflexia episodes, 10 minutes | 13 with no control, 3 reactive (5 s delay, ILLUSTRATIVE), 0 predictive |
| Tests | 241 passing, 16 of them in the safety suite |

## 5. What did not work

- **Predictive stimulation brought no gain on the OpenSim body.** Raised-foot toe height fell
  from 12.69 to 11.83 cm. An earlier claim of improvement is retracted. A small gain remains on
  the simpler Hill twin only (drag 23.6% to 22.2%).
- **Bayesian search showed no sample-efficiency advantage on the synthetic stimulation space.**
  At 20 queries it found 31% against 40% for random search. It remains a method to test on real
  mapping data.
- **Auto-mapping recovers its own assumption.** It proves the code, not a clinical mapping.
- **A learned policy did not robustly beat a simple integral controller.**
- **The organ models are reduced models.** The contrast they show is partly built into them.

## 6. Mock versus real

| Component | In BSO | What real use would require |
|---|---|---|
| Patient controller | software model of commands and answers | the manufacturer's device, process and regulatory path |
| Intent decoder | scripted | a real decoder |
| Stimulation biophysics | recruitment curve and current-spread model | real recruitment data |
| Stimulator | software model | a real platform, under its maker's control |
| Body | reduced and published models | clinical validation |
| Autonomic circuits | reduced models | urodynamics and circuit data |

## 7. The ask

A 30-minute conversation about the lived experience of a patient-side controller, and an
experience review of this nonconnected demo. The author asks for no device access, no
protocol information and no reverse engineering, and claims no clinical result or pilot.

## 8. Run it

```
python3 web/server.py
```

Then open `http://localhost:8765`. `scientific_basis.md` maps design decisions to the
literature. `validation.md` compares each number with its reference range.
