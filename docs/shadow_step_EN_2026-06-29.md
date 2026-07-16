# Shadow Step — explained

**BSO's first own invention, built and validated on the digital twin.**
For: Igor Sharanda · 2026-06-29 · all numbers ILLUSTRATIVE (research simulation)

---

## In plain words

When a person with a stimulator walks, the system has to fire **on time** — lift the foot exactly as the leg starts to swing. Today almost all systems are **reactive**: a sensor sees the foot already starting to drag, and only then adds stimulation. The catch: muscle does not switch on instantly — between command and actual force there is an **electromechanical delay** (≈50–120 ms in real muscle). So a reactive correction is always a little **late**.

**Shadow step** is our idea: don't wait for the drop. The system reads the internal **gait phase clock** (it already knows the intent to "walk" and the step rhythm) and lifts the foot **ahead of time**, leading by exactly that delay. And once the foot has cleared, it **eases off** the now-unneeded stimulation at the end of the phase. So it does not "give more current" — it **redistributes** it in time.

A picture: the reactive controller runs behind and patches; the shadow step walks ahead and prepares the ground.

---

## How we honestly tested it

We did not take it on faith — we **ran an experiment** on the body twin. Three identical arms, everything the same (same body, same intent, same safety limits); only the correction strategy differs:

- **CPG** — no corrections at all (baseline);
- **Reactive** — today's way: correct after the sensor sees a drop;
- **Shadow step** — our invention: anticipate and redistribute.

On **two bodies**: an "instant" one (no delay) and a **Hill-muscle** one — a muscle model with its **own** activation dynamics, so the physiological delay arises **by itself**, not hand-added.

## Result

| Body | Reactive (drag / stim) | Shadow step (drag / stim) |
|---|---|---|
| Instant (no delay) | 14.5 % / 1048 | 14.5 % / **984** |
| **Hill-muscle (real delay)** | 23.6 % / 1056 | **22.2 % / 984** |

Read it like this:
- **With no delay there is nothing to anticipate.** Reactive is no worse; shadow step is just a bit leaner. Honest.
- **With a real delay** (and a living body has one) — reactive is always late, and **shadow step wins: less foot drag (−6 %) with LESS stimulation (−7 %)**.

That is the goal of the invention — **better gait for less current**. And we did not claim it, we **showed** it on the twin.

---

## What it honestly means (and the limits)

- It does **not restore walking** by itself. It is one brick — making each step cleaner and cheaper in current, once stimulation already works.
- The gain is still **modest** (single-digit %) and on a **simplified** twin. Next step: the full validated OpenSim model (18 Hill muscles), where the effect should be sharper.
- All numbers are **illustrative** — a simulation, not a clinical result and not a medical device.
- The real value here is the **method**: we can take an idea, run an honest experiment, find the condition under which it works (and say so plainly when it doesn't). That makes us a lab, not a talking shop.

---

## Under the hood (for a CTO — this is not pictures)

- **Real code, not a slide.** The logic lives in `src/bso/feedback.py` (the predictive mode reads the CPG phase clock and leads by the delay); the electromechanical delay is in the spinal-cord model `src/bso/runtime.py`.
- **The experiment is reproducible:** `scenarios/predictive_step.py` prints the table; run it and you get the same numbers.
- **Locked by tests:** `tests/test_predictive_step.py` — 4 tests guarding against regression (including "on the physiological body the shadow step cuts drag for less stim"). Full suite: **184 tests green**.
- **Visible live:** the dashboard gained a **"Shadow step (invention)"** tab — click it and you see the comparison and an ankle-angle chart (screenshot below).
- **The real-vs-mock line is kept:** intent decoder and patient are simulation; the delay is a physiological model; the stimulator is software.

![Shadow Step demo in the BSO dashboard](/Users/igorsharanda/Desktop/BSO_Тіньовий_крок_демо.png)

*Chart: left-ankle angle over two gait cycles. Grey — reactive, cyan — shadow step; dashed line — the foot-drag threshold. The cyan curve lifts the foot earlier and dips less.*
