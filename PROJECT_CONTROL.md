# BSO project control

**Goal:** a four-screen, explicitly simulated demonstrator of a patient-led controller resilience and session-awareness concept, plus a partner package. No connection to any real device.

**Done criterion:** a first-time viewer understands both pains unaided in WebKit on desktop and mobile; every external claim has evidence or a hypothesis label; the owner's published programs are labelled as his; owner approves the package.

**Route and evidence:** `docs/rework_plan_2026-11-02.md`. Owner version: `~/Desktop/BSO_План_доопрацювання.pdf`.

## Active block

<!-- IHOR_BLOCK_PROGRESS:START v1 -->
Block: B2-SCREENS
- [ ] Primary navigation is four screens: Overview, Controller, Session, Research; all legacy tabs stay reachable from an Archive
- [ ] Controller shows the owner's real programs and requested / acknowledged / failed / unknown states; connection loss never renders as OFF
- [ ] Session covers reminder timer, acknowledgement, unanswered and connection-loss scenarios
- [ ] Forgotten-controller scenario is playable end to end
- [ ] Assistant closed by default, opens only on request
- [ ] Walking model from real simulation trajectories with its label
- [ ] WebKit click-through at 1440 and 390 px and full pytest green
<!-- IHOR_BLOCK_PROGRESS:END -->

Check set: pytest, WebKit on the changed path. Codex: yes, product block, one review with phase 4.

## Owner decisions

- 2026-11-02, direction accepted: patient-led controller concept via clinic and University of Louisville, not a direct pitch of a control program to Medtronic.
- 2026-11-02, real programs stay public. Owner's words: "це мої дані ... я маю право свої дані публікувати ... Тому мої дані залишаємо." This is his own data, published by him. It covers no other person. It overrides fictional programs in the plan. Simulated results stay labelled as simulated. `CLAUDE.md` invariant 7 needs a matching wording change, which requires his authorization for configuration edits.

- 2026-11-02, focus: "не потрібно мені ускладнювати життя ... йти, когось питати ... зробити крутою, з крутим інтерфейсом, з крутим функціоналом, і щоб цьому вразило Луївський ... університет". Build the program first. Outreach, clinic and legal questions do not block the build and are not raised again until the product is ready.

## Next block

Phase 3 visual rebuild, then phase 4 review.

## Latest handoff

2026-11-02: B1-TRUTH closed: AD metric counts episodes and converges (none 13, reactive 3, predictive 0 at dt 0.1; reactive delay 5 s is ILLUSTRATIVE), public copy corrected, explicit decision required, 209 tests green, WebKit checked on banner, guard and programs. Stale figures remain in `docs/partner_brief*.md` and `docs/validation.md`; phase 5 rewrites them. Nothing pushed or deployed. `QA_FINDINGS.md` carries a modification from another tool; leave it alone. Branch `claude/new-session-p6xmtv`.
