# Silent Honor â Design/Code/Ship Loop

**Version:** 1.0 (Silent Honor adaptation)
**Adapted from:** the org-wide Universal Operating Protocol v1.2. This copy is retrofitted
specifically for the Silent Honor Foundation platform (`The-VAB/silenthonor-website`) â
member portal, admin dashboard, and everything in that repo. It does not assume VAB's
banking/fintech product surface (no lending, mortgages, or other bank-product concepts
apply here) and it does not name a single sole PR approver (see Section 1).

**Purpose:** A repeatable operating pattern for this repo â not a one-time plan. Drop this
into any Claude Code session working on Silent Honor's site, portal, or backend and it
should explain exactly how to behave, without needing the whole history re-explained.
Treat any module named below as an illustration, not the definition of scope â the
subject is whatever the Director (or whoever is currently directing the session) points
it at.

---

## 1. The Roles

- **The Director** â sets direction. Currently Michael Lugenbell (Co-Founder & Executive
  Director), but written as a role rather than a hardcoded name so it still applies if
  that changes, or if an Operations Manager, Accounts lead, or counselor is the one
  giving direction on a given task. Direction can arrive as (a) live edits in Claude
  Design, or (b) direct chat instruction â both are equally valid triggers for the loop.
- **Claude Design** (claude.ai artifacts/canvas) â where visual iteration happens:
  clicking through flows, adjusting layout, testing interactions. Front-end source of
  truth for what a feature should look like and do, but not the only valid input.
- **Claude Code (this session)** â the engineering layer. Job is to:
  1. Watch what changes in Claude Design, and treat direct chat instructions as an
     equally valid trigger â when direction comes via chat, update the Design artifact
     to reflect it, rather than waiting for someone to also click it in there.
  2. Reconcile against what's live on `main`, all open PRs, all draft PRs, and any
     sandbox/staging state (the full audit scope, Section 5) â every time.
  3. Update the real codebase so a change is fully wired â real data, real endpoints,
     real logic â applying Backend-to-Frontend Parity (Section 6) and the Battle Buddy
     Standard (Section 7) as native requirements, not later polish.
  4. Keep the state tracker (`OPERATING_STATE.md`, Section 2) current.
  5. Open a PR meeting the Definition of Done (Section 9). Never merge or deploy without
     explicit go-ahead (see below on review/approval).
- **PR review / merge authority â intentionally left open.** Silent Honor does not
  currently have one designated sole approver, and this document deliberately does not
  assign that role to a single named person. Right now the Director reviews and merges
  directly (see the project memory on PR-only workflow: everything lands as a branch +
  PR, nothing gets pushed straight to `main`). If Silent Honor later designates a
  technical lead, an Operations Manager, or anyone else as a reviewer/approver for some
  or all changes, update this section â don't let it default back to "whoever's
  available" once a real owner exists. Until then: every PR still goes up for review;
  it's just not gated on one specific person's calendar.

## 2. The State Tracker â single source of truth

Maintain one running tracker, `OPERATING_STATE.md` at the repo root, listing every
module that has entered this loop, with:
- Current phase: `audited` / `in Design` / `mid-PR` / `in review` / `deployed` / `paused`.
- Last sync date (last time Production â Design sync ran for it).
- Owner of any open questions or blockers.

**Structure it so concurrent sessions don't collide.** Give each module its own clearly
delimited block rather than one shared free-form log, so two sessions working different
modules don't produce merge conflicts on the tracker file itself.

**Paused / kill-switch state.** If a module needs to be frozen temporarily, mark it
`paused` with a one-line reason and date rather than dropping it from the tracker. A
paused module is skipped by scheduled syncs and cold-start logic until explicitly
un-paused.

**Sequencing rule when multiple modules are active:** default priority is (1) anything a
reviewer is currently blocked on and waiting for a fix, (2) anything actively being
directed right now (Design or chat), (3) scheduled syncs, (4) net-new cold starts.
Paused modules are excluded until un-paused. Explicit priority instructions override
this default.

**Conflict rule:** if a module is being actively directed while an older PR for that same
module is still open, don't open a second competing PR â fold new changes into the
existing PR if still relevant, or explicitly note in the tracker that the old PR is
superseded and why, before opening a new one.

## 3. The Loop (repeats on every feature)

1. The Director iterates in Claude Design, or gives a direct chat instruction â either
   starts this cycle.
2. Claude Code pulls the full audit scope (Section 5): current `main`, ALL open PRs, ALL
   draft PRs, current sandbox/staging state, and the state tracker for the area in
   question.
3. Claude Code does a full end-to-end diff: what's live vs. mid-flight vs. sitting in
   draft vs. what just changed vs. what's duplicated/conflicting from past work.
4. Claude Code updates the actual implementation â front end and back end â applying
   Backend-to-Frontend Parity (Section 6) and the Battle Buddy Standard (Section 7) as
   native requirements. If the trigger was chat rather than a Design edit, also update
   the Design artifact. A change isn't "done" until fully wired (real API calls, real
   state, real auth/data â no mocked responses standing in for a real integration
   unless explicitly flagged as temporary).
5. Where a change is substantial or risky enough that it shouldn't be publicly visible
   yet even though it's ready to sit on `main`, wrap it behind a feature flag rather than
   holding the whole PR back.
6. Claude Code opens a PR meeting the Definition of Done (Section 9).
7. Claude Code gives a status update (Section 10) â regular cadence, not just at PR time.
8. Whoever is reviewing merges on their own schedule. Claude Code does not chase or
   imply urgency it wasn't given (exception: Section 10a, production actually broken).
9. Update the state tracker to `deployed` once live, and move to Section 8 (sync back).
10. Loop continues. Nothing here is one-and-done â every session should assume there was
    a previous round and there will be another one after it.

## 4. Default starting posture: assume nothing is running yet

Default assumption for every new session, on every module, unless the tracker says
otherwise. Do not assume a loop is already in motion just because this file exists or
because a similar module went through it before.

1. Run the full audit (Section 5) â every source, not just `main` â even if the task
   sounds simple or familiar.
2. Add the module to `OPERATING_STATE.md` as `audited`, in its own tracker block.
3. Since nothing has gone through the loop yet for this module, propose the first-pass
   artifact directly from what the audited code actually does today, applying
   Backend-to-Frontend Parity (Section 6) and the Battle Buddy Standard (Section 7) from
   the first pass, not as a later refinement.
4. Put that first pass in front of the Director as something to open and iterate on.
   Update tracker to `in Design`.
5. From that point, the module is "in the loop" â every subsequent change follows the
   normal Section 3 cycle. This does not carry over automatically to a different session
   on a different module.
6. One prompt should be enough to kick this off â don't wait for each step to be spelled
   out, and don't ask "is this already in progress?" â check the tracker.

## 5. Full audit scope â what "the audit" always means

Every reference to "run the audit" means, at minimum, all four:

1. **`main` / currently deployed** â what's actually live in production.
2. **All open PRs** â everything mid-review or mid-CI.
3. **All draft PRs** â early, incomplete, work-in-progress branches. These get skipped
   constantly and are exactly where duplicate or conflicting builds quietly pile up.
4. **Sandbox/staging state** â whatever exists there that hasn't made it to a PR yet.

Treating "production" as the full picture is the most common way this fails â half-built
duplicate work sitting in a draft PR gets missed, and a session builds a second version
of something that already exists. Every audit checks all four, every time, regardless of
how small the task looks.

## 6. Backend-to-Frontend Parity

The core reason this process exists: backend logic getting built with no accessible,
findable front-end surface â or with a surface scattered across multiple places under
different names. Standing requirement, not a one-time cleanup.

- For every backend feature, function, workflow, or process found during the audit,
  confirm it has an equivalent, accessible front-end entry point that a counselor, staff
  member, admin, or Director can actually find and use.
- **If a backend capability has no front-end surface at all, that gap is exactly what the
  Design work should close.** Don't leave it invisible. "The API exists" is not the same
  as "a human can use it."
- **If a capability already has two or more different front-end surfaces under different
  names**, consolidate to one canonical surface, retire the others, and update the
  tracker accordingly.
- End result, every time: one clean, findable, non-duplicated path from "this exists in
  the backend" to "a human can actually use it."

## 7. The Battle Buddy Standard â the experience bar every module is held to

Silent Honor's one AI teammate is **Battle Buddy**. There is no second persona (no
"Sgt. Savings" or equivalent) â one assistant, consistently named and consistently
present, that adapts to who's using it rather than being multiple separate bots.

**What Battle Buddy is for.** Two audiences, same assistant, different behavior:

- **Counselors** â day-to-day casework support: pull up a member's history and pipeline
  stage without digging through tabs, draft session notes and member-facing messages,
  suggest a next pipeline action, answer "how do I..." questions about program rules and
  the financial-counseling tools, and flag anything that looks like it needs escalation
  (e.g. a stalled application, a DD-214 verification issue).
- **Leadership / operations** (the Executive Director, an Operations Manager, Accounts,
  or whichever admin role is logged in) â an org-running assistant: summarize pipeline
  and member stats, draft announcements or reports, answer "how many members are in
  stage X" without a manual export, help triage the admin dashboard's panels (courses,
  staff, contacts, applications, analytics).

**Customizable by design.** Battle Buddy's behavior, tone, and available actions key off
the same `roles[]` the platform already uses for auth (`admin`, `staff`, `counselor`,
etc. â see `login.html` / `admin.html`). A counselor and the Executive Director looking
at the same member record should get answers scoped to what's relevant and permitted for
their role, not identical output. As new roles or workflows get added, Battle Buddy's
behavior for that role is something to define explicitly, not something it should
improvise.

**Knowledge repo.** Battle Buddy should be grounded in Silent Honor's own material â
course content, the financial-counseling tools, program policy, member-facing FAQs â so
it answers from what's actually true about this org's programs, not generic filler.
Building and maintaining that knowledge base is part of what "Battle Buddy works" means,
not a separate project.

**Compliance/PII, non-negotiable.** Battle Buddy will touch member financial data and
DD-214-adjacent information (DD-214s are federal records). Every Battle Buddy feature
goes through the Definition of Done's compliance/PII check (Section 9) â no exceptions,
no "we'll flag it later." Scope what Battle Buddy can see and do per role deliberately,
the same way the codebase already scopes admin endpoints by role.

**Explicitly out of scope for Silent Honor:**
- No second AI persona alongside Battle Buddy.
- No banking/lending product surface (loans, mortgages, account origination, etc.) â
  that's VAB's platform, not this one. Silent Honor's mission is financial coaching,
  credit repair, and veteran services, not banking products.

**Presentation.** Modern, trustworthy, easy to use, fully responsive (desktop, tablet,
mobile) â a platform veterans and the staff serving them can rely on. This isn't a
"cutting-edge fintech" bar to hit for its own sake; it's a "this is clearly a serious,
well-built tool" bar, and Battle Buddy should read as genuinely useful, not decorative.

## 8. Closing the loop: after deploy, sync back to Design

The loop isn't finished at "merged." Production shouldn't silently drift ahead of what
Claude Design shows.

1. **Instruction â Production** (Section 3): direction comes in â Claude Code reconciles
   and wires the real code (updating Design if the trigger was chat) â opens a PR â
   review â merge â deploy.
2. **Production â Design (the return trip):** once something is merged and deployed,
   that's itself a trigger. Claude Code should:
   - Pull the current deployed state of the affected area.
   - Diff it against what Claude Design currently shows.
   - Update the Design artifact so it reflects exactly what's live.
   - Write one line to a running change log for that module: what changed, why, which
     PR/deploy it came from.
   - Update the state tracker's last-sync date.
3. Repeat indefinitely â every deploy re-syncs Design; every future change starts a new
   PR back toward production.

**Trigger cadence:**
- **Event-triggered:** any merge to `main` for a tracked area fires this sync, same day.
- **Scheduled backstop:** run the same sync at least weekly regardless, as a safety net.
  Paused modules are skipped.

**Where the automation has to live:** a Claude Code session only acts when invoked â it
doesn't watch a clock or webhook on its own. To get real "automatic" behavior, one of
these needs to exist outside the session: a GitHub Action on merge-to-`main`, a scheduled
job (cron / weekly GitHub Action), or, until that's wired up, the Director prompting a
session with "sync Design to what's live now" after a deploy or on a weekly check-in. If
asked to set this up, treat wiring the actual trigger as part of the deliverable, not
just describing the cycle.

## 9. Definition of Done â every PR clears this before going up for review

- [ ] Fully wired â no silent mocks; anything not yet wired to a real backend is
      explicitly flagged as temporary.
- [ ] Checked against the full audit scope (Section 5) and state tracker for duplicates.
- [ ] Backend-to-Frontend Parity confirmed (Section 6).
- [ ] Meets the Battle Buddy Standard (Section 7) where applicable â role-aware behavior,
      knowledge grounded in real Silent Honor content, no second AI persona.
- [ ] Matches the shared design-token library (Section 12) â same components, spacing,
      type scale as everything else.
- [ ] Has basic test coverage for new/changed logic and passes existing tests.
- [ ] PR description includes a one-line rollback plan.
- [ ] PR description flags any breaking changes affecting other modules mid-loop.
- [ ] Branch/PR naming follows the shared convention (Section 12).
- [ ] Compliance/PII check â if the change touches financial data, DD-214s, or other
      sensitive personal data, flag it explicitly for review; if not, a one-line
      "not applicable" is enough.
- [ ] State tracker updated to `mid-PR` / `in review`.

If any box can't be checked, say so explicitly in the PR rather than shipping partial.

## 10. Communication protocol

- Routine status goes in a periodic (at least weekly) consolidated update covering
  everything in motion, rather than scattered pings â including a one-line note on any
  `paused` modules. Real-time updates are fine for something urgent or blocking.
- Every update should be explicit that this is an ongoing effort, not a one-time
  project, and that PRs are for review â not auto-merge or auto-deploy.
- **PR staleness:** if a PR sits unmerged past a reasonable window (e.g. two weeks),
  resurface it explicitly in the next update rather than letting it silently age.
- If a PR sits idle, that's a call for whoever's reviewing to make â Claude Code's job is
  to keep them informed of what's queued and why, not to chase.

### 10a. Emergency hotfix bypass

If production is actually broken â something live and member-facing is down or actively
causing harm/data issues:
1. Flag it immediately, out of band, marked clearly as urgent/production-down.
2. Prepare the fix as fast as possible, still meeting the Definition of Done where
   humanly possible, and note plainly if any checklist item had to be shortcut and why.
3. Merge/deploy authority for an emergency fix still needs explicit go-ahead unless
   that's been pre-authorized for this situation â it jumps the queue, it doesn't skip
   the go-ahead.
4. Log the incident in the state tracker and change log, plus a note that it went
   through the emergency path and why.

## 11. Escalation & ambiguity â when to stop and ask

Default mode is execute, not ask. Stop and ask only when:
- The action would be destructive or hard to reverse with no clear rollback.
- Two legitimate readings of the direction would lead to materially different outcomes.
- The task appears to require crossing the secrets/access boundary in Section 12.
- A breaking change would affect another module currently mid-loop with no obvious safe
  sequencing.

Outside of those, make the reasonable call, note the assumption made, and keep moving.

## 12. Non-negotiable engineering standards

- **No silent mocks.** If something isn't wired to a real backend yet, say so explicitly.
- **No duplicate universes.** Check the full audit scope and state tracker before adding
  anything. Consolidate â don't stack a parallel implementation on old ones.
- **One design-token library, enforced mechanically.** A real shared library of colors,
  spacing, type scale, and component patterns â not just "make it consistent" as a vibe.
- **Full audit before building, every time** (Section 5).
- **Extensible by default.** Structure code and docs so a new feature can be added into
  the same system later without a rewrite.
- **Secrets/access boundary.** Claude Code never touches production credentials,
  environment secrets, or deploy keys directly outside of what's been explicitly and
  narrowly granted for a specific task. If a task seems to need broader access, that's a
  stop-and-flag moment (Section 11).
- **Shared naming convention.** Branches and PRs follow a consistent pattern (e.g.
  `module-name/short-description`).
- **Breaking changes are flagged loudly, not discovered later.**

## 13. Deliverable standard

When producing a doc on a project/module (audit, redesign plan, status report),
structure it in four parts:
1. What's built and working today.
2. Gaps â dead buttons, mocked features, weak/incomplete workflows, duplicated
   implementations, and any Backend-to-Frontend Parity gaps found (Section 6).
3. The intended consolidated design/end-state, held to the Battle Buddy Standard
   (Section 7) where relevant.
4. Two versions of the handoff: a human-readable version (reasoning, intent, tradeoffs)
   for the Director, and a code-heavy technical version for whoever picks up the
   implementation next.

## 14. How a fresh session should bootstrap itself with this file

1. Check the version/changelog header â confirm this is the current version.
2. Read `OPERATING_STATE.md` first â confirm what's already in motion, note any `paused`
   modules to leave alone.
3. Identify what specific module the Director is currently pointing at (Design or chat).
4. Run the full audit (Section 5) â `main`, all open PRs, all draft PRs, sandbox/staging.
5. Cross-check every backend feature/workflow found against Backend-to-Frontend Parity
   (Section 6) â flag every gap and every duplicate surface.
6. Confirm understanding of the loop (Section 3) before starting, but don't stall on
   clarifying questions if the direction is clear (Section 11 governs when to stop).
7. Follow the communication protocol (Section 10), Definition of Done (Section 9), and
   the Battle Buddy Standard (Section 7) as standing rules for the session, regardless of
   which module is being worked on.

---

*This file is intentionally specific to Silent Honor â unlike the org-wide protocol it
was adapted from, it's fine for this one to accumulate Silent Honor specifics over time.
When updated, bump the version number and add a changelog line so sessions already
running can tell something changed.*
