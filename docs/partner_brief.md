# Brain-Spine Orchestrator (BSO) — Partner Brief

> **Research simulation / digital twin of an adaptive orchestration layer for the
> stimulation side of a brain-spine interface (BSI).** This is **not** a medical
> device and contains no real-hardware, implant, or patient-data code. All numeric
> values are **ILLUSTRATIVE**, not clinically validated.
>
> Concept & author: Ihor Sharanda (1TMO / Unbroken, Ukraine). Built as a working
> proof-of-concept and collaboration instrument — not a finished product.

*(Цей бриф — англійською, бо адресований міжнародним партнерам. Українська версія —
на запит.)*

---

## 1. Position in one paragraph

Walking after spinal cord injury via a brain-spine interface has been demonstrated
(a landmark peer-reviewed study, *Nature* 2023; leading clinical research centers; a partner platform ARC). The open frontier
is **not** "can a person be made to step" — it is **adaptive orchestration**: holding
gait quality in real time against fatigue, parameter drift, balance perturbation and
noisy feedback; coordinating dozens of muscle groups; and doing all of it *inside a
hard safety envelope*. BSO is that orchestration layer. It is designed to sit **on top
of** a real stimulation platform (e.g. the partner platform), not to duplicate it.

Crucially, the same substrate addresses **autonomic function** — bladder, bowel and
sexual function — which people with SCI rank *as highly as, or above, walking*.

## 2. Architecture (deterministic, safety-first)

```
Decoder(0) → CPG Orchestrator(1) → Effectors(2) → [Safety Supervisor(5): veto]
   ↑                                                         ↓
Feedback(3) ← sensor corruption ← Body (kinematic OR MuJoCo physics) ← spinal cord
   ↑                                                  (recruitment + fatigue + coupling)
Adaptation(4): integral OR learned policy        + Autonomic layer (bladder/bowel/erectile)
```

- **Safety supervisor** has absolute veto over every stimulation command (hard limits,
  charge/charge-density, thermal proxy, **autonomic-dysreflexia watchdog**, e-stop). No
  agent can bypass it. No LLM is ever in the real-time motor loop.
- Gait is modelled **phase-wise (CPG)**, physiologically faithful, not a naive
  muscle→voltage map.
- Body backend is swappable behind one interface: a fast kinematic model **or** a
  dynamic **MuJoCo** planar biped with body-weight support.
- **One substrate for locomotion and autonomic function:** the autonomic loop
  (bladder/bowel/erectile) runs on the *same* bus, tick-loop and **SafetySupervisor**
  — autonomic stimulation passes through the same safety veto, and the supervisor's
  autonomic-dysreflexia watchdog is driven by real organ state (trips on dyssynergic
  high pressure, silent under coordinated voiding).

## 3. What is demonstrated (measured in-sim; ILLUSTRATIVE)

| Capability | Result |
|---|---|
| Closed-loop walking (kinematic) | cadence ~76 steps/min, L/R stance antiphase, balance 100% |
| Walking on **dynamic MuJoCo physics** | upright (pelvis 0.90 m, trunk <6°), GRF ≈ body weight, stance alternation −0.96, **0 safety violations** |
| Resilience to fatigue+drift (adaptation) | foot-clearance retention: nominal 100% → degraded 30% → **degraded+adapt 61%** (kinematic); **77% → 98%** on physics |
| Robustness to noisy/dropping sensors | retention **~100%** with adaptation + sensor noise on physics |
| Active balance recovery (physics) | trunk push: **14.8° peak with active loop vs 41.3° passive-only** |
| **Autonomic — bladder** | dyssynergia: 94 cmH₂O, 184 mL residual, **autonomic dysreflexia +51 mmHg** → coordinated EES: **54 cmH₂O, 0 mL residual, no AD** |
| Autonomic — bowel / erectile | coordination restores complete evacuation / functional tumescence |
| Validated OpenSim model | our gait drives `gait10dof18musc` (18 Hill muscles) → physiologically-plausible muscle-tendon excursions on real anatomy |
| **Muscle-driven forward dynamics** | legs move under the 18 Hill muscles from our excitations → alternating gait (L/R hip corr ≈ −0.7), body-weight supported — not prescribed kinematics |
| Autonomous mapping (GP-BO) | recognized method (Bonizzato 2023), validated on benchmark (≈100% vs ≈22% random); sample-efficient, safe-from-query-1 |
| Safety coverage | 16 exhaustive safety tests; 84 tests total, all green |

## 4. Honest mock-vs-real map

| Component | In BSO (mock) | Needed from a partner |
|---|---|---|
| Intent decoder | scripted / stub | cortical decoder (ECoG, e.g. a cortical decoder) |
| EES biophysics | recruitment curve + current-spread coupling | real recruitment data, spinal-circuit models |
| Stimulator | software model | stimulation platform (the partner platform) |
| Body | kinematic / Hill muscles / MuJoCo / **validated OpenSim gait10dof18musc (18 muscles)** | clinical validation; full muscle-driven FD; Rajagopal full-body model |
| Autonomic circuits | reduced physiological models | sacral/lumbar circuit data, urodynamics |
| Regulatory | — | IDE / CE / MDR pathway |

## 5. Honest findings — what works and what doesn't

We report negatives as plainly as positives.

- **Adaptation works and is robust.** A slow Layer-4 controller compensates fatigue/drift
  and tolerates sensor noise, on both kinematic and physics bodies, within the safety
  envelope. An honest trade-off is visible: compensation accelerates fatigue.
- **Learning does *not* universally beat a hand-tuned integral controller.** We built a
  trainable Layer-4 (CEM-optimised policy) and found the simple integral controller is a
  strong, near-optimal baseline for single-objective compensation. The learned policy
  shows an edge **only** in a narrow channel-coupling-dominated, fatigue-free regime, and
  transfers worse to physics. This is a useful result: it tells us *where* learning is and
  is not justified, and the harness is ready for the richer settings where it should pay
  off (high-dimensional channel coordination, partial observability, clinical multi-cost).
- **Active balance** clearly outperforms passive support under perturbation.
- **Autonomic coordination** produces the clinically meaningful contrast (low-pressure,
  complete bladder emptying; prevention of autonomic dysreflexia).

## 6. Ukraine's unique contribution

- A large SCI cohort — including a substantial **military** population — is a world-class
  dataset for training and validating an adaptive layer. This is what a research center/a partner platform do *not*
  have, and what their approach needs to scale.
- The concept author is **both a patient and the architect** — a rare point of trust and
  insight for a collaboration.

## 7. The ask

A joint pilot: **our adaptive orchestration layer + your stimulation platform + the
Ukrainian cohort.** Concrete first technical steps already scoped: MuJoCo PD-tracking is in
place; next are an OpenSim musculoskeletal backend, multi-channel coordinated control, and
training the adaptive layer on synthetic → consented real data.

---

*Deeper reading:* **`scientific_basis.md`** maps every design decision to the primary
literature (Capogrosso 2016, a published trial (2018), Rowald 2022, a landmark study (2023), Squair 2021,
Moraud 2016, published spinal-stimulation studies bladder scES, the <40 cmH₂O upper-tract criterion, AD definition — verified
DOIs/PMIDs). **`validation.md`** checks that the simulation's emergent numbers land in
physiological ranges (cadence, GRF ≈ body weight, safe bladder pressure <40 cmH₂O,
AD ≥20 mmHg).

*Reproduce every figure in this brief:* `python3 scenarios/generate_all.py` (writes to
`outputs/`). **Live interactive demo** (zero dependencies, runs offline):
`python3 web/server.py` → `http://localhost:8765` — crank fatigue / coupling / adaptation /
body model and watch the walking figure, ground reaction force and bladder pressure /
autonomic-dysreflexia risk respond in real time. Safety invariants and the full canon:
see `CLAUDE.md`.
