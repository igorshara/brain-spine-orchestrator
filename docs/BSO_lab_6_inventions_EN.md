# BSO Lab — six inventions for walking recovery

**Brain-Spine Orchestrator** · Igor Sharanda · 2026-06-29
*Research simulator (digital twin). Not a medical device. All numbers ILLUSTRATIVE.*

---

## What it is and why it matters

BSO is a software orchestration layer between a brain intent decoder and a spinal stimulator. But the point of this document is not the program — it is the **method**: we take a recovery idea, run an honest experiment on a **real-physics digital twin of the body**, find the condition under which it works (and say so plainly when it doesn't), and lock it with a test.

In one session the inventor team generated and **proved six original inventions**. Each runs on real code, with a reproducible experiment, guarded by automated tests. **206 tests green.** Everything is clickable live in the dashboard (a tab per invention) and drills down to the source code.

This makes us a **lab**, not dreamers: idea → test → truth, in minutes, with zero risk to the patient.

---

## 1. Shadow step — less foot drag for less current

**Idea.** Don't react to foot-drop after a sensor sees it (always late, due to the muscle's electromechanical delay) — read the gait phase clock and lift the foot **ahead of time**, easing the unneeded late tail.

**Result.** On the physiological Hill-muscle twin: drag 23.6%→22.2% with **less** stimulation (1056→984). Confirmed on the **validated OpenSim model** (18 muscles): mean toe clearance 4.56→4.82 cm.

**Honestly.** With no delay there is nothing to anticipate (a tie) — the win is conditional on the delay. Numbers illustrative.

![](/Users/igorsharanda/Desktop/BSO_Тіньовий_крок_демо.png)

---

## 2. Use-driven assist — help less, recover more

**Idea.** The goal is not movement with stimulation ON but lasting recovery (function with it OFF). Nerves recover use-it-or-lose-it, so the assist level is a knob.

**Result.** Full assist (machine does everything) gives R=0.03 — ~**32x less** lasting recovery than fading assist (R=0.90). The optimum is interior; the best protocol is **assist-as-needed** (reduce help as recovery grows).

**Honestly.** A plasticity model, not clinical proof. But the direction contradicts the "more stimulation = better" intuition.

![](/Users/igorsharanda/Desktop/BSO_Доза_від_зусилля_демо.png)

---

## 3. Hand pacer — the arms carry the rhythm

**Idea.** After SCI the leg decoder is unreliable; the arms are spared. Phase-lock the gait clock to the arm rhythm.

**Result.** Leg decoder stuck at 60 steps/min while the patient speeds up to 84: the free clock stays at 59.8 (error 24), the **hand pacer hits 83.7** (error 0).

**Honestly.** A real opt-in orchestrator feature; default behaviour unchanged.

![](/Users/igorsharanda/Desktop/BSO_demo_handpacer.png)

---

## 4. Dual lock — same force for less charge

**Idea.** One EES channel must both prime the network and execute the move — over-driving and bleeding current onto the antagonist. Split the roles: subthreshold EES priming + a selective peripheral pulse with no spillover.

**Result.** Same net force: at realistic current spread (0.3) — **−25% charge and zero spillover**. The worse the spread, the more it saves (0%→9.5%, 40%→34%). Less charge = less dysreflexia and habituation.

**Honestly.** The model assumes priming shifts the recruitment curve — a hypothesis for the lab.

![](/Users/igorsharanda/Desktop/BSO_demo_duallock.png)

---

## 5. Sensory balance — why sensation keeps you standing

**Idea.** Standing is an inverted pendulum. To hold it you must sense not just tilt position but the **rate of sway** (proprioception) to catch the fall early.

**Result.** Under equal pushes: no sensation topples (328°), position-only falls (39.5°), **proprioception stands** (8.3°). This is sensory ataxia (the Romberg test).

**Honestly.** I first checked the existing twin — its trunk is over-stable and unsuitable; I built a correct inverted-pendulum model instead and left the realtime code untouched.

![](/Users/igorsharanda/Desktop/BSO_demo_balance.png)

---

## 6. Reflex amplifier — let the living loop stand

**Idea.** Below the lesion the reflex arc is alive. Rather than draw support with current, EES raises the **gain** of the load→extension loop so a small intent yields full support.

**Result.** Gain window 0.8–0.9: a small drive of 0.1 is amplified **×3.8** into support. Below — insufficient; from 1.0 — **clonus** (the delayed loop oscillates). EES as a gain knob, not a muscle driver.

**Honestly.** A simplified loop model; the point is to show the window exists between "too weak" and "clonus".

![](/Users/igorsharanda/Desktop/BSO_demo_reflex.png)

---

## Summary and an honest stance

| # | Invention | Proved | On |
|---|---|---|---|
| 1 | Shadow step | less drag for less current | Hill + OpenSim |
| 2 | Use-driven assist | full assist = ~32x less recovery | plasticity |
| 3 | Hand pacer | arms carry cadence through a bad decoder | closed loop |
| 4 | Dual lock | −25% charge, 0 spillover | recruitment |
| 5 | Sensory balance | proprioception = standing | inverted pendulum |
| 6 | Reflex amplifier | small intent → support ×3.8 | delayed loop |

**What it gives.** Six independent levers that compose into one path: bypass the lesion in time (1, 3), save charge and stay safe (4, 6), restore sensation for standing (5) and — above all — optimise not a crutch but **recovery** (2).

**What it does NOT give.** None of these is clinical proof — it is simulation on a digital twin. Numbers are illustrative. Real decisions only with a clinician and within registered trials.

**What we need.** A partner with a stimulation platform and real recruitment data to move these six hypotheses from the twin into the lab. The architecture and experiments are ready; the first steps are scoped.
