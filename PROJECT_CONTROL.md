# BSO project control

**Goal:** a four-screen, explicitly simulated demonstrator of a patient-led controller resilience and session-awareness concept, plus a partner package. No connection to any real device.

**Done criterion:** a first-time viewer understands both pains unaided in WebKit on desktop and mobile; every external claim has evidence or a hypothesis label; the owner's published programs are labelled as his; owner approves the package.

**Route and evidence:** `docs/rework_plan_2026-11-02.md`. Owner version: `~/Desktop/BSO_План_доопрацювання.pdf`.

## Active block

<!-- IHOR_BLOCK_PROGRESS:START v1 -->
Block: B4-PACKAGE
- [x] README, `docs/validation.md` and the partner briefs match the current product: no retracted or unsupported claim, figures reproduced from code
- [x] One-page English summary as a final PDF on Desktop, with a Ukrainian translation
- [x] 60-second demo script that follows the real screens, checked against them
- [x] Letters to University of Louisville and Medtronic, with Ukrainian translations, sending nothing
- [x] Package checked: control figures match the code, PDFs open and read clean, pytest green
<!-- IHOR_BLOCK_PROGRESS:END -->

Check set: pytest, deterministic reproduction of each quoted figure, PDF render inspected. Codex: no, documents. Nothing is sent or deployed in this block.

B2-SCREENS and B3-VISUALS closed: Codex GO at f752025 (review bd87b33c5948, owner-authorized round 3), no findings.

## Owner decisions

- 2026-11-02, direction accepted: patient-led controller concept via clinic and University of Louisville, not a direct pitch of a control program to Medtronic.
- 2026-11-02, real programs stay public. Owner's words: "це мої дані ... я маю право свої дані публікувати ... Тому мої дані залишаємо." This is his own data, published by him. It covers no other person. It overrides fictional programs in the plan. Simulated results stay labelled as simulated. `CLAUDE.md` invariant 7 needs a matching wording change, which requires his authorization for configuration edits.

- 2026-11-02, focus: "не потрібно мені ускладнювати життя ... йти, когось питати ... зробити крутою, з крутим інтерфейсом, з крутим функціоналом, і щоб цьому вразило Луївський ... університет". Build the program first. Outreach, clinic and legal questions do not block the build and are not raised again until the product is ready.

- 2026-11-02, labirynt exposure: `labirynt/` (a separate private app) sat in this public repository with its active PIN in the README and a gate bypass. Owner's answer: the couple has already opened it ("Уже відкрили"), so the live site and PIN stay unchanged. Removed from this branch and its history; the working copy is `~/claude-projects/labirynt`.

- 2026-11-02, Codex round 2 NO-GO at 82ba35b (review 5356a7a05240), then one owner-authorized round. Owner's words: "Так, давай я дозволяю тобі все доробити." Fixed before round 3:
  - P1 switch-off could be refused by the safety check (`src/bso/patient_link.py`). It delivers no stimulation, so the supervisor no longer vetoes it; regression test added.
  - P1 the assistant stated "0 episodes vs 377" (`src/bso/dashboard_agent.py`). Figures now come from the same simulation as the Research charts: 13 with no control, 0 with prediction. "Validated" and "24/7" claims removed from its copy.
  - P2 the Research walking stage now shows a loading text; fixed because the owner asked to finish everything.

## Next block

Delivery of the new site to the live URL, on the owner's word. Stage 2 auto-tuning stays deferred.

## Latest handoff

2026-11-02: B4-PACKAGE closed. Added `/healthz` (d437d80, separate commit, not live until deployed). Package in `~/Desktop/BCI/BSO — Пакет 2026-11` (summary, 60-second demo script, letters to University of Louisville and Medtronic, each EN + UA); sources in `~/Desktop/BCI/Код та робочі матеріали/package_2026-11`. Demo path walked in WebKit by real clicks at 1440 px, 0 page errors, test server stopped, port closed; narration 134 words, timing by word count, not rehearsed aloud. pytest 242 passed. June package and the letter with the retracted pilot claim moved to `~/Desktop/BCI/_Архів`. Nothing sent, nothing pushed, nothing deployed: the letters link the live URL, which still serves the old build. Next: owner's word on push, merge and deploy.

2026-11-02: Codex round 3 GO at f752025, no findings. B2 and B3 closed. Phase 5 package started as B4-PACKAGE. Nothing deployed; the live URL still serves the old build.

2026-11-02: corrective for Codex round 2 done. pytest 241 passed; WebKit by real clicks at 1440 and 390 px, 14 ok, 0 fails: 12 Increase/Decrease pairs then Switch off stops the implant, assistant matches `/api/guardian`, Research shows loading then the walker. Round 3 authorized by the owner and is the last. Nothing deployed.

2026-11-02: branch rewritten without labirynt and force-pushed (82ba35b, tree identical to the pre-rewrite HEAD, PIN absent from history, local backup branch `backup/pre-labirynt-rewrite`). Codex round 2 NO-GO with two P1, see Owner decisions. Waiting for the owner's decision. Review block item stays open; nothing deployed.

2026-11-02: Codex round 1 NO-GO, one corrective made: backup controller refuses everything except off, bladder charts carry labelled references, labirynt removed from the branch history. pytest 239 passed; click-through 114 ok; backup path 12 ok by real clicks. Branch force-pushed by owner's decision. Round 2 is the last.

2026-11-02: B2-SCREENS and B3 visuals built. Click-through 114 ok, 0 fails at 1440 and 390 px; pytest 237 passed before the last JS-only change. One earlier run failed on a button detached mid-click with machine load above 11; it did not recur in two later runs, so it is unproven, not fixed. Knee range fixed with joint stops; the Shadow Step claim was retracted because its test failed afterwards (raised-foot toe 12.69 to 11.83 cm); owner must hear this. Next: Codex review.

2026-11-02: B1-TRUTH closed: AD metric counts episodes and converges (none 13, reactive 3, predictive 0 at dt 0.1; reactive delay 5 s is ILLUSTRATIVE), public copy corrected, explicit decision required, 209 tests green, WebKit checked on banner, guard and programs. Stale figures remain in `docs/partner_brief*.md` and `docs/validation.md`; phase 5 rewrites them. Nothing pushed or deployed. `QA_FINDINGS.md` carries a modification from another tool; leave it alone. Branch `claude/new-session-p6xmtv`.
