# BSO project control

**Goal:** a four-screen, explicitly simulated demonstrator of a patient-led controller resilience and session-awareness concept, plus a partner package. No connection to any real device.

**Done criterion:** a first-time viewer understands both pains unaided in WebKit on desktop and mobile; every external claim has evidence or a hypothesis label; the owner's published programs are labelled as his; owner approves the package.

**Route and evidence:** `docs/rework_plan_2026-11-02.md`. Owner version: `~/Desktop/BSO_План_доопрацювання.pdf`.

## Active block

<!-- IHOR_BLOCK_PROGRESS:START v1 -->
Block: B3-VISUALS
- [x] Blender system scene on Overview, labelled as an illustration, with four parts explained in order
- [x] Every chart carries units, a labelled baseline, sample count, source and a table of the numbers
- [x] Charts drawn at real pixel width, legible at 390 px; programs table closed by default
- [x] A refused or overlong run shows no state and offers a restart; the walker stage shows a loading state
- [x] WebKit click-through at 1440 and 390 px and full pytest green
- [ ] Phase 4: one Codex review of B2 and B3 together, at most two rounds
<!-- IHOR_BLOCK_PROGRESS:END -->

Check set: pytest, WebKit on the changed path. Codex: yes, product block, one review covering B2 and B3.

## Owner decisions

- 2026-11-02, direction accepted: patient-led controller concept via clinic and University of Louisville, not a direct pitch of a control program to Medtronic.
- 2026-11-02, real programs stay public. Owner's words: "це мої дані ... я маю право свої дані публікувати ... Тому мої дані залишаємо." This is his own data, published by him. It covers no other person. It overrides fictional programs in the plan. Simulated results stay labelled as simulated. `CLAUDE.md` invariant 7 needs a matching wording change, which requires his authorization for configuration edits.

- 2026-11-02, focus: "не потрібно мені ускладнювати життя ... йти, когось питати ... зробити крутою, з крутим інтерфейсом, з крутим функціоналом, і щоб цьому вразило Луївський ... університет". Build the program first. Outreach, clinic and legal questions do not block the build and are not raised again until the product is ready.

## Next block

Phase 5 partner package, after the phase 4 review closes. Stage 2 auto-tuning stays deferred.

## Latest handoff

2026-11-02: B2-SCREENS and B3 visuals built. Click-through 114 ok, 0 fails at 1440 and 390 px; pytest 237 passed before the last JS-only change. One earlier run failed on a button detached mid-click with machine load above 11; it did not recur in two later runs, so it is unproven, not fixed. Knee range fixed with joint stops; the Shadow Step claim was retracted because its test failed afterwards (raised-foot toe 12.69 to 11.83 cm); owner must hear this. Next: Codex review.

2026-11-02: B1-TRUTH closed: AD metric counts episodes and converges (none 13, reactive 3, predictive 0 at dt 0.1; reactive delay 5 s is ILLUSTRATIVE), public copy corrected, explicit decision required, 209 tests green, WebKit checked on banner, guard and programs. Stale figures remain in `docs/partner_brief*.md` and `docs/validation.md`; phase 5 rewrites them. Nothing pushed or deployed. `QA_FINDINGS.md` carries a modification from another tool; leave it alone. Branch `claude/new-session-p6xmtv`.
