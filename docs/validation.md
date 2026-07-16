# Quantitative validation — do the sim's numbers land in physiological ranges?

A digital twin is only credible if its emergent quantities sit in plausible
physiological ranges. Below, each BSO output is compared against a reference range.
**All BSO values are ILLUSTRATIVE** and are produced by the listed scenario;
references marked ✓ are verified primary sources (see `scientific_basis.md`), the
rest are textbook/clinical orders of magnitude. The point is *calibration*, not a
claim of clinical accuracy.

## Locomotion

| Quantity | BSO output | Plausible reference | Scenario |
|---|---|---|---|
| Cadence (assisted walking) | ~76 steps/min | slow/assisted gait ~40–80; normal ~100–120 | `walk.py` |
| Gait phasing | stance ≈60% / swing ≈40%, L/R antiphase (corr −0.96) | stance ~60% / swing ~40% | `walk_mujoco.py` |
| Peak ground reaction force | ~470 N vs body weight ~490 N (≈1.0×) | ~1.0–1.2× body weight in walking | `walk_mujoco.py` |
| Trunk lean during gait | <6° | near-upright | `walk_mujoco.py` |
| Active balance vs passive (push) | 14.8° vs 41.3° peak tilt | active control rejects perturbation | `balance_recovery.py` |

## Stimulation envelope (safety limits, `config/limits.py`)

| Parameter | BSO hard limit | Typical EES range | Note |
|---|---|---|---|
| Amplitude | ≤ 20 mA | ~0.5–16 mA (real programs) | ILLUSTRATIVE ceiling, contains real 12–16 mA |
| Pulse width | ≤ 700 µs | ~100–1000 µs (real 550–600) | ILLUSTRATIVE, contains real programs |
| Frequency | ≤ 120 Hz | ~10–90 Hz (real programs) | ILLUSTRATIVE |
| Autonomic frequency | 30 Hz default | bladder-optimal ~30 Hz ✓ | published spinal-stimulation studies |
| Charge per phase | ≤ 12 µC (20 mA × 700 µs = 14 µC abs.) | real 16 mA × 600 µs = 9.6 µC ✓ | ILLUSTRATIVE, real programs pass |

## Autonomic — bladder (`autonomic_demo.py`)

| Quantity | Dyssynergia (no EES) | Coordinated EES | Reference | 
|---|---|---|---|
| Peak detrusor pressure | ~94 cmH₂O ⚠ | ~54 cmH₂O | safe storage **<40 cmH₂O** ✓ (published criterion) |
| Post-void residual | ~184 mL (incomplete) | ~0 mL (complete) | low residual is the goal |
| Autonomic dysreflexia | systolic **+51 mmHg** | +0 mmHg | AD defined at **≥20 mmHg** ✓ (StatPearls/AUA) |
| Trigger | bladder distension below lesion | controlled | most common AD cause ✓ |

Interpretation: the dyssynergic case breaches *both* the upper-tract pressure
threshold and the AD blood-pressure threshold — exactly the clinically dangerous
state — while coordinated neuromodulation stays under both. The contrast is the
clinically meaningful one, with thresholds taken from the literature.

### Closed-loop bladder management (`managed_bladder.py`, 10-min session)

| Quantity | Managed (auto-void) | Unmanaged dyssynergia |
|---|---|---|
| Void cycles | 2 (volume-triggered, before the reflex) | reflex only |
| Peak detrusor pressure | ~52 cmH₂O (safe) | ~97 cmH₂O ⚠ |
| Max volume | ≤250 mL (bounded) | ~300 mL |
| Autonomic dysreflexia events | **0** | ~1875 |

A fill-sensing controller voids by volume / timed schedule / proactive AD-guard
*before* the uninhibited reflex fires, keeping pressure safe and preventing AD
across every cycle — the clinical bladder-management workflow, closed-loop.

## Adaptation & robustness (honest)

| Claim | Evidence | Honesty note |
|---|---|---|
| Adaptation retains gait under fatigue | clearance retention 30%→61% (kinematic), 77%→98% (physics) | trade-off: compensation accelerates fatigue (shown) |
| Robust to sensor noise/dropout | ~100% retention with noise + adaptation | `stress_physics.py` |
| Learned policy beats hand-tuned | **No — not robustly.** Integral baseline wins broadly | reported as a negative result |

## Coverage

16 exhaustive safety tests; **69 tests total, all green**; ruff clean. Every figure
regenerates via `python3 scenarios/generate_all.py`; live demo via `web/server.py`.

---

*Caveat: these are calibration checks of a simulation, not clinical validation.
Clinical accuracy requires real recruitment data, urodynamics and a consented cohort
(partner-side). See `partner_brief.md §4`.*
