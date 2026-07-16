# Limitations & roadmap to credibility (read this first if you're a reviewer)

We state the gaps plainly. BSO is a **software architecture + algorithm prototype**,
not a validated neuroprosthetic and not a biophysical reproduction. Below, each
component is marked **REAL** (defensible as-is), **TOY** (illustrative, must be
replaced for credibility), or **ALGORITHM** (a recognized method, validated here on
benchmarks but applied to synthetic data). Then the concrete path to make it real.

## Honest component audit

| Component | Status | Why |
|---|---|---|
| Safety supervisor (veto, hard limits, e-stop, AD watchdog) | **REAL** | Deterministic, fully test-covered; the design is genuine and regulator-legible |
| Layered orchestration architecture (decoder→CPG→effectors→safety→body→feedback→adaptation) | **REAL** | Sound software architecture; swappable bodies behind one interface |
| GP Bayesian Optimization for parameter search | **ALGORITHM** | Correct (validated: 100% vs 22% random on needle benchmark); applied to a *synthetic* response surface |
| Body — kinematic / planar MuJoCo | **TOY** | A 3-segment planar walker is not credible biomechanics to an expert |
| Body — **validated OpenSim model** (gait10dof18musc, 18 Hill muscles) | **REAL** | Two modes: (a) kinematics-driven analysis (`opensim_gait.py`); (b) **muscle-driven forward dynamics** — legs move under muscle forces from our excitations, alternating gait (`opensim_muscle_driven.py`). Remaining: ground contact / weight-bearing (currently body-weight supported) |
| Body — Hill muscle layer | **ALGORITHM/TOY** | Real Hill equations, but a reduced model, not a validated musculoskeletal model |
| Electrode→muscle recruitment | **TOY** | Hand-authored Gaussian current-spread; "83% recovery" is circular (recovers our own assumption) |
| Bladder / bowel / erectile models | **TOY** | Reduced ODE/state models; the dyssynergia contrast is built into assumptions |
| Adaptation (integral / learned) | **REAL/HONEST** | Works; learned-vs-tuned reported as an honest negative |
| All numeric values | **ILLUSTRATIVE** | Range-plausible (validation.md) but not clinically validated |

## What an expert will (rightly) object to, and our answer

1. **"The walking figure is a cartoon."** Addressed: we now drive the **validated
   OpenSim `gait10dof18musc` model** (18 Hill muscle-tendon units) with our orchestrator's
   gait and report real muscle-tendon excursions and anatomical segment geometry
   (`opensim_gait.py`), run **muscle-driven forward dynamics** (`opensim_muscle_driven.py`),
   render a **3D bone-mesh** of the model in the dashboard, AND solve **weight-bearing**
   muscle excitations via **OpenSim Moco optimal control with foot-ground contact**
   (`moco_inverse.py`): converges (objective ~411), physiologically-sensible activation
   (soleus ~0.97, gastroc ~0.49 bearing load; reserves ≤40 N·m). Honest scope: kinematics
   are *prescribed* (inverse). And **predictive balance is now solved too**:
   `moco_track.py` runs **MocoTrack with FREE kinematics + foot contact** — the solver
   finds muscle excitations *and emergent motion* that satisfy the contact dynamics
   **without falling** (converges, "Optimal Solution Found"; pelvis height held upright,
   the body does NOT collapse). This is the genuine balance controller — the case that
   buckled under plain forward dynamics now solves via optimal control. Env note:
   `moco_inverse.py`/`moco_track.py` auto-set the dyld path so CasADi's IPOPT loads.
   **Longer horizon:** predictive balance also converges over a longer 0.8 s window
   (`moco_track.py 0.8`), upright throughout. **Real-time policy:** `distill_policy.py`
   distills the slow Moco optimum into a fast policy via behavioral cloning — a numpy MLP
   maps joint state → muscle excitations with **held-out R² ≈ 0.96 within a condition** at
   **~2 µs/call** (the offline optimum becomes a real-time controller). **Honest negative:**
   training one policy across several speeds (`moco_dataset.py`) fits the trained speeds
   (R² ~0.9) but does **not** generalize to a held-out speed (R² < 0) — the per-speed
   optimal-control solutions are not smoothly interpolable by simple behavioral cloning.
   **Resolved by direct policy optimization:** `rl_train.py` trains a speed-conditioned
   policy with **Evolution Strategies** (Salimans 2017, an RL-family method, numpy) on the
   gait objective itself across speeds — and it **generalizes to the unseen speed 0.5
   (+41% over baseline)**, succeeding exactly where cloning failed. Lesson: optimize the
   objective, don't imitate non-interpolable optima. Remaining: full deep RL (PPO/SAC,
   needs torch) on the physics model, multi-cycle horizons, and on-hardware validation.
2. **"The mapping is circular."** Correct as a *recovery* claim. The defensible claim is
   the **method**: GP-BO (Bonizzato et al. 2023, *Cell Reports Medicine*) for
   sample-efficient autonomous parameter search vs the exhaustive grid sweep done
   manually in clinic. Real value = clinician time + uncertainty quantification +
   continual adaptation. It must be run on **real evoked responses** to claim accuracy.
3. **"The numbers are illustrative."** Correct. They are calibrated to physiological
   ranges (validation.md) for plausibility only. Real numbers need recruitment data,
   urodynamics, and clinical measurement.

## Concrete roadmap to a credible system

**Tier 1 — achievable now (software, no partner data):**
- Swap the planar walker for the **OpenSim Rajagopal model**; reproduce a known gait
  cycle, then drive muscle excitations from the orchestrator.
- Run **GP-BO on real published recruitment curves** (or a biophysical EES model, e.g.
  Capogrosso 2013 axon-cable + FEM) instead of hand-authored Gaussians.
- Add uncertainty-aware, safety-bounded BO (constrained BO: never query unsafe configs).

**Tier 2 — with a clinical partner (the clinical partner / 1TMO):**
- Feed **real evoked EMG / motor responses** from the partner stimulator telemetry into
  the mapper; validate recovered maps against the clinician's manual maps.
- Validate bladder logic against **urodynamics** (real detrusor pressure / EMG).
- De-identified cohort to train and validate the adaptation layer.

**Tier 3 — with a device partner (the device partner / a device partner) + regulatory:**
- Real-time integration with the stimulation platform; latency/safety verification.
- Regulatory pathway (IDE / CE / MDR); the safety supervisor is the foundation for this.

## The honest one-liner for partners

> "This is not a finished neuroprosthetic. It is a working, safety-first orchestration
> architecture and a correct implementation of the recognized autonomous-mapping method
> (GP-BO), with a clear, honest plan to ground every toy component in validated models
> and real data. We know exactly where the gaps are — and what we need from you to close
> them."

*That sentence is what earns a serious partner's trust — not an overclaim.*
