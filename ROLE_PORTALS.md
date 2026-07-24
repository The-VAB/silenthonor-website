# Role Portals -- Silent Honor Foundation

Companion to `SILENT_HONOR_OPERATING_PROTOCOL.md`. Section 7 of that doc researched what
each staff role *does* and what Battle Buddy should do for them; this doc turns that into
the **portals** -- the actual place each role logs into and works from. One portal per role,
tailored to that role, with access following the same hierarchy as Battle Buddy.

**Status:** spec / in Design. This is the plan the portal builds follow, not a record of
built work. See the state tracker for what's actually built.

---

## 1. The access model (same hierarchy as Battle Buddy)

When someone is assigned a role, that role determines which portal they land in and what
tools they see. The hierarchy mirrors the Battle Buddy capability grants exactly, so the
two stay consistent:

| Role | Portal they land in | Tool access |
|---|---|---|
| **Executive Director** (admin) | ED portal (`admin.html`) | **Everything** -- every tool in every portal below |
| **Operations Manager** | Operations portal | Own tools **+ Counselor + Fundraiser** tools; everything except ED-only (board/governance) |
| **Financial Counselor** | Counselor portal | Counselor tools only |
| **Fundraiser / Development Mgr** | Development portal | Development tools only |

This is enforced two ways, and both matter:
- **Routing** -- on login, role decides the landing portal (this partly exists: `login.html`
  already routes admin/staff -> `admin.html`, counselor -> `counselor-portal.html`).
- **Backend access** -- each API endpoint is gated to the roles allowed to use it. This is
  the piece that makes the hierarchy real rather than cosmetic, and it's the main net-new
  backend work (see Section 4). A hidden sidebar link is not security; the endpoint behind
  it has to enforce the same rule.

A person can hold more than one role (`roles[]` already supports this). The ED viewing the
counselor portal, or an Ops manager helping with fundraising, is expected -- the portals are
views onto one shared system, not walled-off apps.

---

## 2. What exists today (audit, 2026-07-25)

| Portal | State | Files |
|---|---|---|
| ED / Admin | **Exists, comprehensive -- but needs a quality pass (Section 3)** | `admin.html` (~2,600 lines): Overview, Pipeline, Applications, Members, DD-214 Review, Courses, Announcements, Knowledge Base, Messages, Inquiries, Staff, Reports, Audit Log |
| Counselor | **Exists, comprehensive** | `counselor-portal.html`, `counselor-caseload.html`, `counselor-tasks.html`, `counselor-waitlist.html`, `counselor-member.html` (~3,000 lines), `messages.html` |
| Member | Exists | `dashboard.html`, `pending.html` |
| **Operations Manager** | **Missing** | -- |
| **Fundraiser / Development** | **Missing, plus its whole backend is greenfield** | -- (no donor/CRM/grant data model exists at all) |

So the net-new portal builds are **Operations** and **Development**. The existing ED and
Counselor portals aren't a build-from-scratch job -- they're a redesign/quality job (Section 3)
plus filling specific gaps.

---

## 3. The quality bar -- "top-looking, working tools," not a spreadsheet on a page

Director feedback, 2026-07-25, on the existing ED/admin (and accounts) portal: it has the
data, but it reads like *"a spreadsheet put on the thing"* -- it doesn't feel like a real
tool and doesn't function smoothly. Every portal, existing and new, is held to this bar (it
is the Battle Buddy Standard's presentation requirement, applied to the whole workspace):

- **Purpose-built tools, not data dumps.** A table of members is a spreadsheet. A tool is:
  a pipeline board you drag a member through, a DD-214 review queue with the document and
  an approve/deny in one place, a member record that shows the whole story (credit trend,
  session history, tasks) at a glance. Each screen should do a *job*, not just display rows.
- **The important thing is obvious and one click away.** The number that matters is big and
  up top; the action you need is a button, not buried in a menu. Reduce the clicks between
  landing and doing.
- **Smooth and modern.** Real loading states, no full-page reloads to do one thing, clear
  feedback on every action, consistent components from the shared design-token library
  (`css/dashboard.css`, `css/dashboard-widgets.css` -- already used by the counselor portal,
  which is the closer-to-right example to match).
- **Fully responsive** -- desktop, tablet, phone. A staffer checking the pipeline from their
  phone between meetings should have it work.
- **Fast.** Nobody waits on a spinner to see their own caseload.

This applies as a redesign mandate to `admin.html`, and as a from-the-start requirement for
the two new portals -- they should launch at this bar, not get "polished later."

---

## 4. The portals, tool by tool

Each tool below is grounded in the role research in `SILENT_HONOR_OPERATING_PROTOCOL.md`
Sections 7.1-7.4. "Exists" = already built somewhere; "New" = net-new.

### 4.1 Executive Director portal (`admin.html`) -- redesign + fill gaps

The ED sees everything. The work here is (a) the quality pass in Section 3, and (b) adding
the ED-specific tools that aren't there yet.

- **Org dashboard** (Exists, redesign): the KPIs an ED actually reports on -- members served
  vs. capacity, verified/pending, revenue diversification, reserve coverage, grant pipeline
  health, program outcomes -- as real stat tiles and trend charts, not a wall of numbers.
- **Board reporting** (New): assemble a board packet from live data (exec summary, status by
  priority, outcomes, risks, decisions-needed) -- ties into Battle Buddy 7.1.
- **Grant compliance calendar** (New): every grant's report/closeout deadlines with proactive
  flags. Fundraising owns grant *pipeline*; the ED needs the *compliance-deadline* view.
- **Program outcomes** (New/partial): outcome language for funders, not just activity counts.
- **Everything from the Ops, Counselor, and Development portals** (via access), plus the
  existing Members / Pipeline / Applications / DD-214 / Courses / Staff / Knowledge Base /
  Reports / Audit tools -- redesigned to the Section 3 bar.

### 4.2 Operations Manager portal (New)

Ops oversees how the org runs day to day. Access = own tools + Counselor + Development.

- **Pipeline bottleneck board** (New): the member pipeline with stall-detection surfaced --
  "14 applicants stuck in DD-214 review 5+ days" -- so Ops intervenes before drop-off. Built
  on existing pipeline data, presented as an operational tool not a list.
- **Task & SLA oversight** (New, extends existing tasks): every staff/counselor task, what's
  overdue, who owns it, a "what's stuck" digest.
- **Vendor / contract tracker** (New): renewal dates, license/insurance expirations,
  performance-review cycles, flagged before they lapse.
- **Audit-readiness checks** (New): does every active case have its required docs (consent,
  verified DD-214, disclosures) -- a gap list on demand.
- **Staffing/coverage view** (New): counselor capacity vs. intake demand, under-coverage flags.
- **SOP library** (New): the org's documented processes, editable (pairs with the Knowledge
  Base module already built).
- **Plus the Counselor and Development toolsets** via access.

### 4.3 Financial Counselor portal (Exists) -- keep, extend

Already the strongest-built portal (caseload, tasks, waitlist, deep member record). Keep it,
hold it to the Section 3 bar, and add the Battle Buddy 7.3 capabilities as they're built:

- **My caseload / waitlist / tasks / member record** (Exists).
- **Credit report delta view** (New): what changed between two pulls.
- **Dispute workflow** (Partial -> extend): draft FCRA dispute letters (human-reviewed,
  never auto-sent), track the 30/45-day windows.
- **DMP feasibility tool** (New): income/expenses/debts -> sustainable-payment check.
- **Veteran-protection flags** (New): SCRA eligibility, VA-garnishment exemptions,
  predatory-loan patterns.
- **Session notes -> queryable memory** (New): pairs with the Meeting & Session Notes module
  (protocol 7.7).

### 4.4 Fundraiser / Development portal (New -- biggest build, needs a backend first)

This is the largest gap: there is **no donor/prospect/grant/campaign data model in the system
at all today**. The portal can't be built until that backend exists. Spec:

- **Donor CRM** (New backend + New portal): donor/prospect records, 360-degree profile
  (gifts, events, touchpoints), segmentation.
- **Gift entry + acknowledgment** (New): log gifts; draft thank-yous within 48h with correct
  IRS substantiation ($250+, and quid-pro-quo over $75) -- Battle Buddy 7.4.
- **Grant pipeline** (New): LOIs, proposals, deadlines/reporting tracker with alerts.
- **Campaign tracking** (New): appeals, response rate, average gift, retention by segment --
  built around the new-vs-repeat donor retention gap (~19% vs ~69%).
- **Prospect research briefs** (New, internal-only): never donor-facing.
- **Moves management** (New): log each interaction advancing a major-gift relationship.

Compliance baked in from the start: charitable-solicitation registration awareness (41
states + DC), donor-privacy walls on wealth/prospect data, AFP Donor Bill of Rights.

---

## 5. Cross-cutting: the backend access model

The portals are only as real as the endpoint gating behind them. Today, many admin endpoints
are gated `admin`-only (`get_current_admin`); a pure Operations or Development role would be
blocked. Making the hierarchy in Section 1 real requires a deliberate pass over the API:

- Define the role set the system recognizes (`admin`/ED, `operations`, `counselor`,
  `development`, `staff`, `member`) and which endpoints each may call.
- Apply the hierarchy: ED = all; Ops = all but ED-only; Counselor/Development = their own.
- This is the honest prerequisite for the Ops and Development portals -- without it, a new
  portal either can't reach its data or has to over-grant admin rights. It's a focused
  backend task and should land before (or with) the first new portal.

---

## 6. Build roadmap (suggested sequencing)

1. **Backend role-access model** (Section 5) -- unblocks everything else; do first.
2. **ED/admin quality redesign** (Section 3 + 4.1) -- highest daily-use surface, and the
   thing the Director specifically called out as feeling like a spreadsheet. Biggest
   immediate payoff.
3. **Operations Manager portal** (4.2) -- mostly aggregates existing data; achievable once
   the access model exists.
4. **Development backend + portal** (4.4) -- largest effort; the donor CRM is effectively a
   new subsystem. Its own multi-step build.
5. **Counselor portal extensions** (4.3) -- fold in as the matching Battle Buddy capabilities
   get built.

Each of these is its own module in the state tracker and its own PR (or set of PRs). None is
a one-session job; the ED redesign and the Development backend especially are substantial.
