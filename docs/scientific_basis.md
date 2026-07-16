# Scientific basis & design rationale

*Each major design decision in BSO is mapped to the primary literature it is
grounded in. Citations were verified against primary sources (DOI / PubMed) in
June 2026. BSO is a **research simulation** — it draws on this work for
physiological plausibility; it does not reproduce or claim these results, and all
numeric values remain ILLUSTRATIVE.*

---

## 1. Why an orchestration layer on top of EES (not a new stimulator)

The clinical lineage that restores walking after SCI is **spatiotemporal epidural
electrical stimulation (EES)** of the lumbosacral cord, increasingly driven by a
cortical decoder:

- **Capogrosso et al. 2016**, *Nature* 539:284–288 — a wireless brain–spine
  interface restored weight-bearing locomotion in primates within days, by decoding
  motor-cortex activity and stimulating flexion/extension "hotspots" in the lumbar
  cord. DOI 10.1038/nature20118 (PMID 27830790).
- **Wagner et al. 2018** (a published trial), *Nature* — targeted, movement-timed
  spatiotemporal EES re-established adaptive control of paralysed muscles during
  overground walking in humans. DOI 10.1038/s41586-018-0649-2 (PMID 30382197).
- **Rowald et al. 2022**, *Nature Medicine* 28:260–271 — a purpose-designed
  multielectrode paddle with activity-specific stimulation programs let participants
  stand, walk and cycle within a day (a partner platform ARC lineage).
  DOI 10.1038/s41591-021-01663-5 (PMID 35132264).
- **a landmark study et al. 2023**, *Nature* — a fully-implanted **brain–spine interface**
  ("digital bridge") restored natural, thought-controlled walking, stable over a
  year. DOI 10.1038/s41586-023-06094-5 (PMID 37225984).

**Design consequence:** the hardware path (decoder + stimulation platform) is
demonstrated and is being commercialised (a partner implanted-stimulation platform/the partner platform). The unmet,
software-side need is the **adaptive orchestration** between decoder and
stimulator. BSO targets exactly that layer and is designed to sit *on top of* such
a platform — see `partner_brief.md §1`.

## 2. Why we model gait phase-wise (CPG) and recruit afferents, not muscles

- **Moraud et al. 2016**, *Neuron* 89:814–828 — combined computational modelling and
  experiments showing EES acts **through muscle-spindle (proprioceptive afferent)
  feedback circuits** to modulate locomotor muscle activity; simulation-driven
  protocols then corrected gait/balance deficits. DOI 10.1016/j.neuron.2016.01.009
  (PMID 26853304).
- **Formento et al. 2018**, *Nature Neuroscience* — EES must **preserve
  proprioception** to enable locomotion; stimulation that antidromically collides
  with afferent traffic degrades it. DOI 10.1038/s41593-018-0262-6.

**Design consequence:** our orchestrator (`orchestrator.py`) is a phase-based CPG,
and the spinal-cord stage (`runtime.SpinalCord`) maps stimulation through a
**recruitment curve** to a *net effect*, explicitly documented as a simplification
of afferent recruitment — not a direct muscle drive. This is the physiologically
honest framing, and it is what distinguishes a serious concept from a naive
"muscle → voltage" map. The computational-model + closed-loop tradition above is
the lineage our adaptive layer extends.

## 3. Why the autonomic functions belong on the same substrate

The same EES platform engages **autonomic** lumbosacral circuits — and these
outcomes are ranked by people with SCI as highly as walking:

- **Squair et al. 2021**, *Nature* 590:308–314 — EES protocols restored
  **haemodynamic stability** (a neuroprosthetic baroreflex) in rodents, primates and
  humans, by engaging sympathetic circuits the injury had disconnected.
  DOI 10.1038/s41586-020-03180-w (PMID 33505019).
- **Lumbosacral scES for bladder** (Univ. published spinal-stimulation studies / Kentucky SCI Research Center):
  "Lumbosacral spinal cord epidural stimulation improves voiding function after human
  SCI", *Scientific Reports* 2018 (DOI 10.1038/s41598-018-26602-2); and
  "Targeting bladder function with network-specific epidural stimulation after
  chronic SCI", *Scientific Reports* 2022 (DOI 10.1038/s41598-022-15315-2). Notably,
  systematic frequency testing yielded the **lowest post-void residual at ~30 Hz**.

**Design consequence:** the autonomic loop (`autonomic.py`) runs on the *same* bus,
tick-loop and `SafetySupervisor` as locomotion, and our autonomic stimulation
channels default to **30 Hz** — matching the bladder-optimal frequency above. The
unifying thesis ("one orchestration layer + one safety gate for motor *and*
autonomic function") is grounded in the fact that the same platform is already used
for both motor and haemodynamic/bladder outcomes.

## 4. Why autonomic dysreflexia is the central safety concern

- **Autonomic dysreflexia (AD)** is a life-threatening, sudden hypertensive episode
  triggered by noxious stimuli (most commonly **bladder/bowel distension**) *below*
  the lesion, in individuals with SCI **at/above T6**. The clinical definition is a
  systolic rise of **≥20 mmHg** (commonly cited 20–40 mmHg) over baseline
  (StatPearls; SCIRE; AUA). Detrusor-sphincter dyssynergia and high storage pressure
  are major contributors.
- **Safe bladder pressure:** McGuire et al. (1981) established that sustained storage
  pressures **>40 cmH₂O** predict upper-urinary-tract deterioration — still the
  clinical rule of thumb (with newer work flagging risk even lower).

**Design consequence:** the `SafetySupervisor` owns an AD watchdog driven by organ
distension (`update_autonomic_dysreflexia`), with `SAFE_VOID_PRESSURE_cmH2O = 40`
and an AD blood-pressure-rise flag. In `autonomic_demo.py`, dyssynergic voiding
breaches both thresholds (≈94 cmH₂O, +51 mmHg) while coordinated neuromodulation
keeps pressure and BP safe — the clinically meaningful contrast.

## 4b. Why autonomous mapping uses GP Bayesian Optimization

Clinicians currently map a 16-contact array (e.g. the partner stimulator) by hand,
sweeping configurations and watching evoked responses — hours, patient-specific.

- **Bonizzato et al. 2023**, *Cell Reports Medicine* — "Autonomous optimization of
  neuroprosthetic stimulation parameters that drive the motor cortex and spinal cord
  outputs in rats and monkeys." Gaussian-process Bayesian optimization (GP-BO)
  autonomously finds optimal stimulation in a *fraction* of the queries an exhaustive
  search needs, online, with uncertainty quantification and continual learning.
  (PMID 37044093; see also the GP-BO STAR Protocols, 2024.) Related: Bayesian
  optimization for neuromodulation parameter selection (U. Minnesota group).

**Design consequence:** `bso/bopt.py` implements a correct GP-BO (RBF kernel + UCB),
**validated on a needle benchmark (≈100% vs ≈22% random at 20 queries)**, and applies
it to autonomous stimulation-parameter search (`bopt_mapping.py`). We report its
sample-efficiency honestly (see `limitations_and_roadmap.md`): the decisive,
literature-validated advantage is in large, high-dimensional, non-stationary *real*
parameter spaces — which a small synthetic surface cannot fully showcase.

## 5. What is honestly *not* grounded yet (mock layer)

- The intent decoder, the EES biophysics, the musculoskeletal body and the autonomic
  circuit detail are **reduced models**, not validated reproductions.
- The "learned vs hand-tuned adaptation" study reports an honest **negative** result
  (the integral baseline is strong) — see `partner_brief.md §5`.
- Real recruitment data, a stimulation platform, urodynamics, and a consented cohort
  are needed from a partner. The mock/real boundary is mapped explicitly in
  `partner_brief.md §4`.

---

*This document is the basis for an external scientific deck. Before any external
use, re-confirm each citation against the primary source.*
