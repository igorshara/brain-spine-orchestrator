# Quantitative validation: do the simulator's numbers land in plausible ranges?

A digital twin is credible only if its emergent quantities sit in plausible physiological
ranges. Each output below is compared with a reference range. **All BSO values are
ILLUSTRATIVE.** Every BSO value was reproduced on 2026-11-02 by running the listed scenario.
References marked ✓ are verified primary sources (see `scientific_basis.md`); the rest are
textbook or clinical orders of magnitude. This is a calibration check of a simulation, not a
claim of clinical accuracy.

## Locomotion

| Quantity | BSO output | Plausible reference | Scenario |
|---|---|---|---|
| Cadence, assisted walking | 76 steps/min | slow or assisted gait ~40–80; normal ~100–120 | `walk.py` |
| Left/right stance alternation | correlation −0.97 | strong antiphase | `walk_mujoco.py` |
| Peak ground reaction force | 496 N at ~490 N body weight (≈1.0×) | ~1.0–1.2× body weight | `walk_mujoco.py` |
| Trunk lean during gait | 6.8° (95th percentile) | near upright | `walk_mujoco.py` |
| Pelvis height | 0.89 m mean | stays upright | `walk_mujoco.py` |
| Trunk push, active vs passive | 15.0° vs 41.3° peak tilt | active control rejects the push | `balance_recovery.py` |

## Stimulation envelope (safety limits, `config/limits.py`)

| Parameter | BSO hard limit | Typical range | Note |
|---|---|---|---|
| Amplitude | ≤ 20 mA | ~0.5–16 mA | ILLUSTRATIVE ceiling, contains the author's 12–16 mA programs |
| Pulse width | ≤ 700 µs | ~100–1000 µs | ILLUSTRATIVE, contains the author's 550–600 µs programs |
| Frequency | ≤ 120 Hz | ~10–90 Hz | ILLUSTRATIVE |
| Autonomic frequency | 30 Hz default | bladder-optimal ~30 Hz ✓ | published spinal-stimulation studies |
| Charge per phase | ≤ 12 µC | 16 mA × 600 µs = 9.6 µC ✓ | ILLUSTRATIVE, the author's programs pass |

## Autonomic: bladder (`autonomic_demo.py`)

| Quantity | Dyssynergia (no stimulation) | Coordinated stimulation | Reference |
|---|---|---|---|
| Peak detrusor pressure | 94 cmH₂O | 54 cmH₂O | safe storage **<40 cmH₂O** ✓ |
| Post-void residual | 184 mL | 0 mL | low residual is the goal |
| Autonomic dysreflexia | 1 episode, systolic **+41 mmHg** | 0 episodes, +0 mmHg | defined at **≥20 mmHg** ✓ |

Both modelled states exceed 40 cmH₂O at their peak. Coordinated stimulation lowers the
pressure and empties the bladder, but it does not reach the safe storage criterion in this
model. The contrast is built into the reduced model and is not evidence of a clinical effect.

### Bowel and erectile models (`autonomic_demo.py`)

Bowel residual 0.38 vs 0.00. Erectile rigidity 0.00 vs 0.96. Both are normalized outputs of
reduced models.

### Closed-loop bladder management (`managed_bladder.py`, 10-minute session)

| Quantity | Managed (auto-void) | Unmanaged dyssynergia |
|---|---|---|
| Void cycles | 2 | reflex only |
| Peak detrusor pressure | 52 cmH₂O | 97 cmH₂O |
| Maximum volume | 250 mL | 300 mL |
| Autonomic dysreflexia episodes | **0** | **13** |

### Dysreflexia guardian (`ad_guardian.simulate`, 1.5 mL/s fill, 600 s, dt 0.1)

| Policy | Episodes | Peak systolic rise |
|---|---|---|
| None | 13 | +55.3 mmHg |
| Reactive, 5 s delay (ILLUSTRATIVE) | 3 | +55.3 mmHg |
| Predictive | 0 | +0 mmHg |

Episodes replaced an earlier count of threshold-crossing samples, which depended on the time
step and is retracted.

## Adaptation and robustness

| Claim | Evidence | Honesty note |
|---|---|---|
| Adaptation retains foot clearance under degradation, kinematic body | 100% nominal, 27% degraded, 92% degraded with adaptation (`resilience.py`, 30 s) | compensation accelerates fatigue |
| Adaptation retains clearance under fatigue, physics body | 99% nominal, 69% fatigue, 98% fatigue with adaptation (`stress_physics.py`) | balance 0.97 under fatigue, 1.00 otherwise |
| Robust to sensor noise | 98% with fatigue, noise and adaptation (`stress_physics.py`) | synthetic noise model |

## Results reported as negative or conditional

| Claim | Result | Scenario |
|---|---|---|
| Predictive stimulation raises toe clearance on the OpenSim body | **Retracted.** Raised-foot toe 12.69 → 11.83 cm, mean clearance −2.71 vs −2.9 cm, low frames 59 vs 60: no gain | `predictive_opensim.py` |
| Predictive stimulation reduces drag without delay | No: drag 14.5 → 14.5, only effort falls (1047.7 → 983.6) | `predictive_step.py` |
| Predictive stimulation reduces drag with muscle delay | On the Hill twin only: off 26.2, reactive 23.6, predictive 22.2; effort 1055.9 → 983.6 | `predictive_step.py` |
| Bayesian search is sample-efficient on the neurostim space | **Not supported on this space.** 1,440 configurations: 18% vs 5% random at 10 queries, 31% vs 40% random at 20. On the needle benchmark 100% vs 22% at 20 queries | `bopt_mapping.py` |
| Auto-mapping recovers contacts | Circular: it recovers the model's own assumption (`program_mapping.py`) | `program_mapping.py` |
| A learned policy beats the integral controller | Not robustly; reported as a negative result | `learn_adaptation.py` |

## Coverage

241 tests, all green, including 16 in `tests/test_safety.py`. Reproduce a figure by running
its scenario. Running scenarios rewrites the tracked `outputs/*.png`.

---

*These are calibration checks of a simulation, not clinical validation. Clinical accuracy
would require real recruitment data, urodynamics and a consented study.*
