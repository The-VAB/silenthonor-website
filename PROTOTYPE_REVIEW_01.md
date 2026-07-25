# Prototype Review 01 -- Director Feedback & Build Directives

Captured from the Director's full walkthrough of the four-portal prototype (2026-07-25).
This is the change list the next build follows. Marks: **KEEP** / **CHANGE** / **ADD** /
**MOVE** / **RESEARCH**.

---

## Cross-cutting themes (apply to every portal)

1. **Every record tool needs its input / CRUD actions.** The #1 note across the whole
   review: *"there's no add button, no way to make changes."* The prototype showed the
   read/display side; the build must add the write side -- Add / Edit / assign forms on
   every tool that holds records (roster, conflicts, agenda, votes, staff, donors, grants,
   tasks, vendors...). Each "Add X" opens a real form; this review notes the fields where
   they matter.

2. **Cross-system push -- actions must propagate (this is the point of one system):**
   - **Roster:** adding a board member pushes to the PUBLIC site's board section
     (`about.html`) with their bio + photo.
   - **Staff:** adding a staff member sends a welcome email + their login credentials and
     provisions their account/role in the system.
   - **Counselor:** anything a counselor does links through to that member's own portal
     view -- except sensitive/internal items that shouldn't be member-visible.
   - **Compliance:** uploading a document to the S3 bucket auto-populates the fiduciary
     compliance calendar (deadlines fill in from the document).
   - **Donations:** a new donation in Zeffy auto-logs as a gift in the Donor CRM.

3. **Named integrations (confirmed with the Director):**
   - **DisputeFox** -- credit disputes (done in prototype).
   - **Zeffy** -- the donation processor Silent Honor actually uses (corrects the earlier
     Stripe/processor assumption). Gifts flow Zeffy -> Development.
   - **QuickBooks** -- accounting.
   - **S3** -- document storage; uploads drive the compliance calendar.
   - **DocuSign** -- e-signature.

---

## Executive Director

- **Overview** -- KEEP. Loved it ("shows everything... pretty much everything I need, I can
  add later").
- **Votes & Resolutions** -- CHANGE/RESEARCH: define HOW votes are collected. Right now it
  only displays results. Need the actual voting mechanism (in-app board voting, or a way to
  record a vote with for/against/abstain per director). No input exists yet.
- **Packet Builder** -- CHANGE: make "pulled from live data" real and explain it -- show
  WHERE each section's numbers come from (program/member/financial data) and what Generate
  produces. Clarify the function.
- **Agenda** -- KEEP + ADD: show the Add Item form and its fields (title, presenter, time
  allocation, notes, attachments). Keep the Battle Buddy prefill of recurring items (liked).
- **Roster** -- ADD an Add-board-member button. On add, PUSH to the public site board
  section with bio + photo (cross-system push above).
- **Committees** -- KEEP as-is for now (org has no formal committees yet; low priority).
- **Conflicts** -- ADD a "Log a disclosure/conflict" button (currently no way to add one).
- **Compliance** -- KEEP (loved). ADD: auto-fill deadlines when documents are uploaded to S3.
- **ED Mode is too thin** (only Financials + Strategy) -- RESEARCH done, EXPAND. A nonprofit
  ED's day-to-day (Indeed/Funding for Good/BoardSource) covers far more; ED Mode should add:
  **Staff / HR** (evaluations, performance, hiring, org chart), **Program Oversight**,
  **Fundraising Oversight** (a rollup of Development), **Cash Flow / Budget**, **External
  Relations / spokesperson**, plus the management dashboard -- each with real input/actions.
- **MOVE Vendors from Operations -> ED.** The ED pays vendors (DocuSign, etc.), not the
  Operations Manager. (See Operations below.)

---

## Operations

- **Dashboard** -- KEEP. Really liked ("I'll be in operations more than ED").
- **Pipeline** -- KEEP.
- **Staffing** -- KEEP + ADD an **Add Staff** button. On add: send a welcome letter + their
  logins, and provision them into the system (role/account). ADD: click a staff member /
  counselor to view their activity and workload.
- **Task Board** -- KEEP (liked To Do / In Progress / Done).
- **SOP Library** -- KEEP.
- **Vendors** -- MOVE to ED (see ED). Clarify: it's for tracking services the org pays for /
  contracts, which is an ED/finance function, not Operations.

---

## Counselor -- MAJOR RESTRUCTURE (two levels)

The Director's key structural note: most counselor tools are member-specific, and having them
all as top-level tabs is "a lot right there." Restructure into two levels:

1. **Counselor's own workspace (member-independent)** -- what they see first: their
   **Overview**, their **Tasks / to-dos**, **Caseload**, **Waitlist**, **Pipeline**. This is
   the counselor's own dashboard of what THEY need to do, not tied to any one member.
2. **Member workspace (opens when they click a specific member)** -- pulls up that member's
   tools: Assessment, Game Plan, Report Analyzer, Simulator, Disputes/DisputeFox, Budget/DMP,
   Debt Payoff, Action Plan, Veteran Benefits, Session Notes -- PLUS that member's own
   dashboard (a per-member overview of what's going on).

So: click Pipeline -> work the pipeline -> click a person -> their full toolset + their
dashboard opens. The overall counselor dashboard stays high-level.

- **Waitlist** -- CHANGE: no cherry-picking clients. Replace with a **"Request Next Client"**
  button -- when a counselor is ready, they click it and the system assigns the next member
  on the waitlist automatically.
- **Counselor actions link to the member's portal** (except sensitive/internal items).
- Everything else in the counselor toolset -- KEEP (has what's needed).

---

## Development

- **Dashboard** -- KEEP (liked).
- **Donor CRM** -- CHANGE: clicking a donor opens a full donor record. RESEARCH done -- the
  record should pull: contact info + communication preferences; full giving history (gifts,
  recurring, receipts, funds supported, campaigns); relationships (household, employer,
  foundation, spouse/solicitor); engagement/activity (events, email engagement, notes, tasks,
  every touchpoint written back automatically); attached documents; custom fields (e.g.
  volunteer interests, veteran affiliation).
- **Log Gift** -- KEEP + integrate **Zeffy**: a new donation in Zeffy auto-logs here.
- **Campaigns** -- CHANGE: currently read-only ("shows you stuff but it's not really a
  tool"). Make it actionable -- create/manage a campaign, set goals, track and act.
- **Grants** -- CHANGE: add click-in detail + actions per funder/stage (currently only a
  dashboard view; can't click into a funder or move a stage). (Director doesn't do
  fundraising, so lower personal priority -- but make it a real tool for whoever does.)

---

## Suggested build order

1. **Counselor two-level restructure** -- biggest structural change; unlocks the cleaner
   model the Director wants. (Counselor workspace -> click member -> member workspace.)
2. **Add/Edit forms across all record tools** (the #1 theme) -- roster, conflicts, agenda,
   staff, donors, grants, votes.
3. **Cross-system pushes** -- roster -> public site, staff add -> welcome + logins, compliance
   <- S3, gifts <- Zeffy.
4. **ED Mode expansion** (Staff/HR, Program, Fundraising rollup, Cash Flow, External) +
   **move Vendors to ED**.
5. **Donor CRM detail view** + **Campaigns/Grants made actionable**.
6. **Votes collection mechanism**.

All of this is prototype-level design first (to react to), then the real backend build per
`SILENT_HONOR_PLATFORM_PLAN.md`.
