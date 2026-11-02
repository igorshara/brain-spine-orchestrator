# BSO rework plan (2026-11-02)

Status: proposed, awaiting owner decisions. Based on `34242c0`, a WebKit capture of all 22 tabs, independent Codex and Gemini reviews, and web research. Owner-facing version: `~/Desktop/BSO_План_доопрацювання.pdf`.

## Decision

Rebuild BSO as a four-screen, explicitly simulated demonstrator of a "patient-led controller resilience and session-awareness concept". It connects to nothing. Move the research content behind an optional area. Do not present it as a control program for a Medtronic device.

## Why this framing

- University of Louisville KSCIRC, with Medtronic, Kessler Foundation and JHU APL, gave a tablet controller for Intellis (Stim X Release 1) to 16 research participants by April 2022. Its stated driver was limited hand function; forgotten controllers and forgotten shutoff are not mentioned. https://medicalxpress.com/news/2022-04-home-epidural-people-spinal-cord.html
- A five-year $7.8M NIH project (2021) with Medtronic develops sensor-driven closed-loop stimulation for locomotion and bladder on commercial stimulators "as an investigational use". This is the owner's Stage 2. https://www.eurekalert.org/news-releases/703965
- Abbott already ships iPhone patient control, so a phone controller alone is not novel. https://apps.apple.com/us/app/id6444318464
- Intellis is indicated for chronic intractable pain. Motor use after SCI is investigational, so a product-team pitch stays on controller behaviour and walking stays in research material.
- Current status of Stim X and the NIH project: not found.

## Target structure

| Screen | Sources | Content |
|---|---|---|
| Overview | flow (rewritten) | The two pains, what this is and is not |
| Controller | cockpit, programs | Fictional programs; requested / acknowledged / failed / unknown states |
| Session | new | User-started reminder timer, acknowledgement, unanswered and connection-loss scenarios |
| Research (optional) | approve, map, plate, sensors, gym, loco, osim | Labelled synthetic examples, walking model |

Archive, out of primary navigation, code kept: frontier, autoclin, urodyn, guard, auto, autotrain, shadow, usedriven, handpacer, duallock, balance, reflex.

Design rules:
- Connection loss never renders as a confirmed OFF.
- Session copy says "time since you started this reminder", never stimulation duration.
- The assistant opens only on request.
- No framework migration: new screens in separate files.

## Findings

| Sev | Finding | Evidence | Fix |
|---|---|---|---|
| P1 | Owner's real stimulation programs are public | Live `GET /api/programs` returned 20 programs with parameters, no auth, on 2026-11-02; `src/bso/stim_programs.py` in a public repo; `CLAUDE.md` invariant 7 and the UI banner say otherwise | Remove from demo, use fictional data; repo visibility is an owner decision |
| P1 | AD headline metric is a numerical artefact | `ad_guardian.simulate`, policy `none`: dt 0.5 gives 377 events, 0.25 gives 1249, 0.1 gives 1246, 0.05 gives 0; peak rise 106.6 to 38.5 mmHg. `autonomic.py:195-197` appends one event per step above the limit | Count episodes and duration, verify convergence, hide the figure until then |
| P1 | Auto-mapping recovers its own assumption | `program_mapping.py:25` derives the "true" contact from character codes of the program text | Label as a synthetic algorithm demo |
| P1 | Unsupported clinical and readiness claims | `web/index.html:323`; `docs/partner_brief_verita_EN.md:147` | Rewrite as simulation-scoped capability statements |
| P1 | Outreach letter claims an active pilot | `~/Desktop/BCI/pdf/07_*.pdf`, "We are piloting with a clinical partner" | Remove unless partners confirm in writing |
| P2 | Assistant covers content; on 390 px nearly the whole cockpit | Screenshot `90_mobile_cockpit.png`; `web/index.html:95` | Closed by default |
| P2 | Duplicated assistant messages, "20.0 real programs", "84 tests" badge against 206 passing, mixed languages | WebKit capture; test run 2026-11-02 | Fix in rebuild |
| P2 | Omitted decision is logged as approve | `web/server.py:800`; `tests/test_clinical_approval.py:35` only checks an empty log | Require an explicit valid decision; add tests |

## Visuals

| Tool | Scope | Required label |
|---|---|---|
| Three.js | Walking model from actual simulation trajectories; electrode inspection; Research only | Simulated movement, not a treatment result |
| Blender 5.2 | One controller, communicator and implant scene at 1080p; primitive mannequin, no downloads | Illustration |
| Charts | Units, baseline, sample count, source; aligned pressure and volume panels | Synthetic data |
| Higgsfield | Not in the first pitch; optional clip up to 30 s at 1080p, estimated $15-50, needs a quote and owner approval | AI-generated |

No generated video is evidence.

## Phases

| # | Scope | Acceptance criterion | Estimate | Codex |
|---|---|---|---|---|
| 1 | Claims, public data, AD metric, labels | Every external claim has evidence or a hypothesis label; no real programs in the public demo; AD metric converges across dt | 1-2 d | with phase 4 |
| 2 | Four screens and failure scenarios | First-time viewer understands both pains unaided; unknown state never shown as confirmed | 4-7 d | with phase 4 |
| 3 | Visual rebuild | Every visual labelled; legible at 390 px | 3-5 d | with phase 4 |
| 4 | WebKit desktop and mobile path tests, full pytest, one review | All scenarios clicked through; tests green; no open P0/P1 | 3-5 d | yes, product block |
| 5 | One-pager, 60 s demo, letters | Owner approves text and disclosure scope | 2-3 d | no, documents |

Stage 2 (auto-tuning) is deferred. It needs clinical data under an authorized study, and this repository stays synthetic. Invariants in `CLAUDE.md` section 1 apply throughout.

## Outreach order (owner sends or approves each message)

1. Implanting clinic: consent, exact device model, Medtronic representative.
2. University of Louisville KSCIRC: 30-minute lived-experience conversation.
3. Medtronic patient-programmer product and human factors: 30-minute experience review of a nonconnected demo.
4. ONWARD Medical, only for research collaboration. ARC-IM is investigational; Empower BP (NCT07147296) is recruiting.

Before the Eureka portal: read its IP terms (not found publicly) and consult a patent attorney. The repository is already public.

## Panel disagreements resolved

| Topic | Codex | Gemini | Resolution |
|---|---|---|---|
| Lead demo | Two-pain journey | Safety plus GP-BO | Codex; the mapping result is circular |
| Autonomic screen | Archive | Keep as hub | Archive; metric unreliable, off-topic for the first ask |
| Higgsfield | Unnecessary | Vision video | Not in first pitch |
| Frontend | Not raised | Migrate to a framework | Rejected for now |

## Unverified

Owner's exact device model; replacement process for a lost controller; timer or cycling fit for the owner's model; Medtronic portal IP terms; causal link between prolonged stimulation and spasms (owner's report, потребує підтвердження); availability of a research interface for Intellis.
