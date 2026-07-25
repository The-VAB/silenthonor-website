# Silent Honor Platform -- Full Build Plan

The deep-dive + design + build plan for the four staff portals, their integrations, and the
cross-cutting features. Companion to `ROLE_PORTALS.md` (tool inventory) and
`SILENT_HONOR_OPERATING_PROTOCOL.md` (Battle Buddy / Major Finance / knowledge base).

**Approach:** one shared system, role-scoped portals. Data enters once at its source
(mostly the member side) and fans out to every tool. Specialist regulated work (credit
disputes, accounting) hands off to the best-in-class tool rather than being half-rebuilt
in-house. Every section gets its own ClickUp-style task workspace. Everything feeds and is
reachable by Battle Buddy (staff AI) and Major Finance (member AI). Built over-complete on
purpose -- the Director trims from a full build rather than guessing from a thin one.

---

## 0. Two ground rules (from Director, 2026-07-25)

**A. Member-side data is the source of truth.** Almost everything the staff portals show
originates from the member: the public signup (`signup.html`) + DD-214 upload, the member
dashboard, member messages, course activity, uploaded documents. Staff portals READ and act
on that data; they do not re-key it. New portal features must pull from the existing member
data model, not create parallel copies.

**B. No conflicts with the existing repo -- integrate, don't collide.** Before building any
portal feature, check what already exists in `The-VAB/silenthonor-website` and build onto it:
- Existing staff surfaces: `admin.html` (ED/admin), the `counselor-*.html` suite, `dashboard.html` (member).
- Existing backend routers: `auth`, `members`, `admin`, `counselor`, `courses`, `disputes`,
  `messages`, `credit`, `staff`, `reports`, `content`, `programs`, `financial_counseling`,
  `knowledge` (the KB module just added).
- Existing data the portals must reuse (not duplicate): `users` (with `roles[]`,
  `pipeline_stage`, `credit_repair_stage`, `financial_counseling_stage`), `disputes`,
  `credit_scores`, `credit_accounts` (game plan), `fc_data` (financial counseling),
  `documents`, `messages`, `tasks`, `course_progress`, `audit_log`, `knowledge_base`.
Every new tool maps onto these. The prototype designs get translated into the existing files
(extend `admin.html` / the counselor suite) rather than new parallel apps, so nothing forks.

**C. Everything integrates with Battle Buddy + Major Finance.** Every tool's data is
reachable by the assistants, scoped by role: Battle Buddy can read/draft against member
records, tasks, disputes, financials, board items, donors; Major Finance answers members
from the member-visible knowledge base + the member's own stage. New features must expose
their data to the AI layer (via the same backend), not be a dead end the assistants can't see.

---

## 1. Integration architecture -- build vs. buy vs. link

The most important design decision: what we build vs. connect to. Each integration has a
direction and a source of truth.

| Domain | Tool | Direction | Why |
|---|---|---|---|
| **Credit disputes / letters** | **DisputeFox** | Portal -> DisputeFox (push items); status back | Generic letters get reduced to codes by **e-OSCAR** and flagged **frivolous**. DisputeFox uses **AI-randomized Metro 2 letters**, AutoFox one-click disputes, USPS mailing, branded client portal -- purpose-built to clear the frivolous problem. We link out; we do NOT generate generic letters in-portal. |
| **Accounting / fund** | **QuickBooks Online** | Development -> QBO (gift/class sync); ED financials read from QBO | QBO is the nonprofit standard; donor CRMs sync gifts via class/fund tracking. Financials tools read from it rather than re-keying. |
| **Donations / payments** | Stripe / donation processor | Processor -> portal | Online gifts auto-create donor + gift records. |
| **E-signature** | DocuSign (already a vendor) | Portal -> DocuSign; signed docs back | Consents, agreements, board resolutions. |
| **Email / SMS** | Resend / SES (already) + SMS | Portal -> provider | Acknowledgments, reminders, messaging. |
| **Credit report pull** | Bureau data provider | Provider -> portal | One-click tri-bureau import feeds Report Analyzer + Game Plan. |
| **Calendar / meetings** | Google / Outlook | Two-way | Sessions, board meetings, agenda. |
| **Knowledge base + AI** | In-house (built) | -- | Battle Buddy + Major Finance draw from it. |

**The rule:** a regulated/specialist workflow with a best-in-class tool (disputing,
accounting, e-sign) -> integrate and show status in-portal; do not reimplement it and inherit
its risks. Silent Honor's own program work (financial counseling, casework, governance,
fundraising) stays in-portal and gets built deep.

---

## 2. Credit vs. financial-counseling split (Counselor portal)

Director feedback, acted on: the in-portal generic dispute letters were too few and would get
flagged. Resolution:

- **Credit repair / disputes -> DisputeFox.** The portal becomes a *handoff + status*
  surface: select flagged items (from Game Plan / Report Analyzer), push to DisputeFox in one
  click, and show dispute status/rounds synced back. Letters are generated by DisputeFox's
  AI-randomized Metro 2 engine, not us. Game Plan, Report Analyzer, and Score Simulator stay
  in-portal (strategy/education, not letter-generation). The member's disputes still live in
  the existing `disputes` collection so Battle Buddy and the member's own view can see status.
- **Financial counseling stays in-portal and goes deeper.** Budget, DMP, debt payoff, action
  plan, goals, savings, cash-flow, veteran-benefit checks, session notes -- Silent Honor's own
  coaching work, expanded, on the existing `fc_data` model. This is where the portal does
  *more*, not less.

---

## 3. Cross-cutting: a ClickUp-style task workspace in every section

Every portal gets its own **Tasks** workspace, on the shared `tasks` collection that already
exists, scoped by role:
- **Views:** a board (kanban by status) and a list; group by status / assignee / due / priority.
- **A task has:** title, assignee, due date, priority, status, linked record (member / donor /
  grant / board item), comments.
- **Statuses per section** (configurable): counselor = To Do / In Progress / Waiting on Member
  / Done; development = Cultivating / Ask Made / Stewarding / Closed; etc.
- **Auto-created tasks** from events: "DD-214 stalled 5 days," "grant report due 9 days,"
  "gift needs acknowledgment (48h)," "dispute round due." (Battle Buddy can open and summarize
  these.)
- **Role-scoped:** counselor sees their tasks; Ops sees all; ED sees org-wide.
- Notifications + a per-person overdue digest.

This is the ClickUp-style layer the Director asked for -- one engine, a tailored view per role,
all reachable by Battle Buddy.

---

## 4. Executive Director -- Board / ED toggle

The ED holds two hats; the portal lets the Director flip between them so neither clutters the
other:
- **ED Mode** -- running the org: Overview, Financials (QBO-fed), Strategy, Tasks, and access
  into the Ops / Counselor / Development toolsets.
- **Board Mode** -- chairing the board: Packet, Agenda, Votes & Resolutions, Roster,
  Committees, Conflicts, Fiduciary Compliance.
One toggle at the top switches which workspace groups show. Overview + Tasks appear in both.
Governance safeguard (ROLE_PORTALS.md Sec. 8) still applies: ED-evaluation / compensation /
ED-conflict route to the Governance Committee.

---

## 5. Per-section deep dive (integrations + tasks + AI folded in)

### Executive Director (Board + ED toggle)
Management: org dashboard (from member/program data), outcomes/funder reporting, **Financials
from QuickBooks**, grant compliance calendar, strategic plan, org-wide Tasks, access to all
portals. Board: packet builder, agenda, votes/resolutions, roster, recruitment matrix,
committees, conflict-of-interest register, policy library, fiduciary compliance calendar, ED
evaluation (-> Governance Cmte), document repository, board Tasks. Battle Buddy drafts packets,
summarizes financials, tracks action items.

### Operations Manager
Pipeline bottleneck manager (from member `pipeline_stage`), staffing/coverage, **Tasks (the
ops command center -- all staff tasks + SLAs)**, SOP library (in the knowledge base),
vendor/contract tracker (renewal + DocuSign), audit-readiness (member document completeness),
+ access to Counselor & Development. Battle Buddy flags bottlenecks and drafts SOPs.

### Financial Counselor
Intake/assessment, member 360 (from member data), **credit repair via DisputeFox handoff**
(Game Plan + Report Analyzer from bureau pull + Score Simulator in-portal; disputes/letters ->
DisputeFox), **financial counseling in-portal and deeper** (budget, DMP, debt payoff, action
plan, goals, savings, cash-flow, veteran-benefit checker on `fc_data`), session notes ->
Battle Buddy memory, per-member Tasks, compliance pre-flight, document vault (DocuSign
consents), secure messaging (existing `messages`).

### Development / Fundraising
Donor CRM (NEW backend) **syncing gifts to QuickBooks**, gift entry + IRS-correct
acknowledgments, grant pipeline, campaign performance + retention, moves management, prospect
research (internal-only), Tasks (moves/asks/stewardship), donation-processor feed. Battle
Buddy drafts acknowledgments, LOIs, appeal copy.

---

## 6. Design / UX plan

- **Workspaces, not tab walls** (pattern already in the prototype). ED adds the Board/ED toggle.
- **One component system** (already built): stat tiles, chart cards, tables, chips, kanban,
  rows, gauges -- reused everywhere so it reads as one product.
- **Integration surfaces are honest:** a tool backed by an integration shows a "connected to
  DisputeFox / QuickBooks" state and a real action (Push to DisputeFox, Sync to QuickBooks),
  not a fake in-house version.
- **Input at the source, fan-out everywhere:** member self-signup, automatic pulls, staff
  logging as they work, one-time import -- never bulk re-keying.
- **Dark command-center aesthetic**, Silent Honor brand, fully responsive, colorblind-safe
  charts (all established in the prototype).

---

## 7. Build sequence

1. **Prototype (design to react to)** -- all four portals + the new features (DisputeFox
   handoff, ED toggle, per-section Tasks, integration surfaces) so the Director can trim/keep.
2. **Backend role-access model** -- the real gate behind the portals.
3. **Shared task engine** -- extends the existing `tasks` collection; powers every section.
4. **Integrations** -- DisputeFox (disputes), QuickBooks (accounting), processor (gifts),
   DocuSign (e-sign), bureau pull (credit), calendar. Each reachable by Battle Buddy.
5. **Development donor/CRM backend** -- the one fully greenfield data model.
6. **Translate each approved portal design into the existing repo files** (extend `admin.html`
   / the counselor suite), wired to the member data model and the AI layer -- no forks, no
   conflicts.

Nothing is a one-session job; this plan is the map the build follows.
