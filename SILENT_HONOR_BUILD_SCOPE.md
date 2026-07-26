# Silent Honor -- Full Build Scope

The master scope for turning the approved prototype into the real, production platform.
Written to be handed to Tyler for the AWS/infra side and to drive the build as a series of
PRs. Companions: `SILENT_HONOR_PLATFORM_PLAN.md` (integrations + stack), `ROLE_PORTALS.md`
(tool inventory), `PROTOTYPE_REVIEW_01.md` (Director's change list),
`SILENT_HONOR_OPERATING_PROTOCOL.md` (Battle Buddy / Major Finance).

Prototype to react to: the four-portal command center (claude.ai artifact). This doc turns
that design into real, workable software.

---

## 0. Confirmed decisions (Director + GitHub audit, 2026-07-26)

- **UI standard = the VAB "ProAble" design system.** Confirmed with the Director that "ProAble"
  lives in the VAB repo. It is **`The-VAB/vab-platform` -> `VAB_DESIGN_DIRECTIVE.md`** (the VAB
  Universal Dashboard Design Directive, 328 directives, added ~Jul 16 2026) plus the
  **`packages/shared-theme`** tokens and the SolidJS component packages. Silent Honor's build
  matches that directive's look and interaction law. (Open item 12.1: confirm this is what the
  Director means by ProAble, and whether to reuse the VAB SolidJS components or port the look
  to vanilla -- see below.)
- **Frontend = vanilla HTML/CSS/JS** (per this repo's Roundtable Verdict 1, which voted 5-of-6
  against a framework rewrite), restyled to the VAB directive and reusing this repo's existing
  shared component system (`js/components.js`, `css/global.css`, `css/dashboard*.css`). Hosted
  on S3 + CloudFront (already live). **Requirement from Director: changes to the LMS, board,
  and staff must push to the public front-end site.**
- **Backend = Rust on AWS Lambda** (aligns with the VAB monorepo: Rust Lambda + Terraform),
  replacing the interim Python/FastAPI/App Runner service over a migration path (Section 11).
- **Secrets = AWS Secrets Manager + IAM roles, NEVER in code.** Tyler owns the AWS setup
  (Secrets Manager, IAM, Lambda, Terraform). Enforced platform-wide (see
  `SILENT_HONOR_PLATFORM_PLAN.md` Section 8).
- **LMS must be fully developed and included** (Director, 2026-07-26). The existing
  `courses.html` / `course.html` / `member-courses.html` / `css/course.css` / `js/course.js` /
  `js/journey.js` / `backend/routers/courses.py` are the base; the LMS gets built out fully.
- **AI: Battle Buddy (staff-facing) + Major Finance (member-facing).** Silent Honor keeps
  "Major Finance" for members, NOT the VAB's "Sgt. Savings" (Director's earlier call). Battle
  Buddy integrates via the VAB `packages/battle-buddy` API contract.
- **Integrations: DisputeFox** (credit disputes), **Zeffy** (donations), **QuickBooks**
  (accounting), **S3** (documents -> compliance calendar), **DocuSign** (e-sign), bureau data
  (credit pull), calendar. Secrets for all live in Secrets Manager; frontend never holds one.

---

## 1. The UI standard to build to (ProAble = VAB Design Directive)

Every staff/member surface follows the directive. The prototype already hits most of this;
the deltas are called out.

- **Three-Zone Layout Law:** left two-tier command rail (Tier-1 domains + Tier-2 contextual
  tree, active path lit, live count badges, Cmd/Ctrl-K search) -- center overview deck (hero
  metric band -> 3-6 bento insight cards -> one activity/priority stream, NO forms in center)
  -- right slide-over drawer for ALL depth (forms, tools, workflows, record detail), with
  Peek/Work/Focus widths, breadcrumb stacking, deep-linkable URLs, autosave-on-close.
  - **Prototype delta:** the prototype puts create/edit in centered modals. **The directive
    mandates the right slide-over drawer, never a centered modal.** Convert the modal engine to
    a right drawer in the build.
- **Record 360 workspace** (Focus-width drawer with tabbed lifecycle) -- the counselor's
  per-member workspace and the donor record map directly onto this pattern.
- **ACTING ON context pill + global Cmd/K command palette** in the header -- one always-mounted
  palette, each module registers its actions; tracks the last-focused record. Backend seam:
  `GET/PATCH /context/current`.
- **Visual language:** dark-mode-first with a polished light mode (`.dark` class on root),
  glass/depth layering, dimensional icons, living/animated data (count-ups, streaming
  sparklines), 150-300ms eased micro-interactions (respect reduced-motion), one variable font
  (**Inter**), bento-grid center, ambient status accent line, **AI presence orb** (Battle
  Buddy / Major Finance as a living animated orb, not a static bubble), recruiting empty states,
  celebration moments (course completed, funded, cleared).
- **Color is functional:** red = at-risk, amber = attention, green = healthy -- separate from
  brand accent.
- **Brand:** Silent Honor keeps its OWN identity (it is a 501(c)(3), not the bank). Adopt the
  directive's structure/patterns/motion, but use Silent Honor's brand tokens (red, navy, gold
  in `css/global.css`) and logo. VAB brand tokens for reference: red `#eb1946`, navy `#061021`/
  `#0d1c32`/`#122740`, gold `#c9a84c`, font Inter. (Open item 12.2: confirm SH keeps its own
  red/navy/gold vs. adopting VAB's exact hexes.)

---

## 2. Architecture

**Frontend** -- vanilla HTML/CSS/JS, S3 + CloudFront.
- Evolve the existing shared system: `js/components.js` (nav/footer injection across the 13
  dashboard pages) becomes the three-zone shell; `css/dashboard-widgets.css` becomes the
  directive's card/drawer/token system (port `packages/shared-theme/theme-variables.css` +
  `toc-shell.css` concepts to vanilla CSS variables). One shared `drawer.js` for the
  slide-over. No build step (per the verdict).
- Each portal is a page (or a shell + role-routed views) that calls the Rust API and renders
  real data. No mock data in production (Definition of Done).

**Backend** -- Rust on AWS Lambda behind API Gateway, Terraform IaC (mirrors the VAB stack).
- Data: reuse the existing collections where sensible (users with `roles[]`, disputes,
  credit_scores, credit_accounts, fc_data, documents, messages, tasks, course_progress,
  audit_log, knowledge_base) and add new ones (donors, board_members, votes, agenda,
  committees, conflicts, vendors, grants, campaigns). DocumentDB (current) or DynamoDB --
  Tyler's call on the AWS side.
- AuthN/Z: the role-access model (see `ROLE_PORTALS.md` Section 5) enforced at every Lambda
  endpoint. ED = all; Ops = all but ED-only; Counselor/Development = own scope; Member = self.

**Secrets** -- AWS Secrets Manager + IAM roles (Tyler). No secret in code, config, client
bundle, or logs. Integrations authenticate server-side (Lambda) only.

**AI layer** -- Battle Buddy service integrated via the VAB `packages/battle-buddy` API
(`battleBuddyApi.ts` / `httpClient.ts` contract); Major Finance as the member-facing assistant
grounded in the member-visible knowledge base. Every tool's data is reachable by the assistant,
role-scoped. AI presence orb per the directive.

---

## 3. Scope by surface

Each is built to "fully workable" (Section 10): every button clickable and routed, real data,
Battle Buddy wired, drawers not modals.

1. **Executive Director portal** -- Board/ED mode toggle. Board: packet builder, agenda,
   votes (real voting mechanism), roster (-> pushes to public board page), committees,
   conflicts register, fiduciary compliance calendar (auto-filled from S3 uploads). ED: org
   dashboard, Staff/HR, Programs, Fundraising rollup, Cash Flow (QuickBooks), Vendors,
   Financials, Strategy, Tasks. Access into all other portals.
2. **Operations portal** -- pipeline bottleneck manager, staffing (Add Staff -> welcome +
   logins + push to public staff page; click a staff member -> their activity), Task Board,
   SOP library (knowledge base), audit-readiness. Full visibility except ED-only items.
3. **Counselor portal** -- two-level: member-independent workspace (Overview, Caseload,
   Waitlist with "Request Next Client" auto-assign, My Tasks) -> click a member -> that
   member's Record 360 (Dashboard + Assessment, Game Plan, Report Analyzer, Simulator,
   Budget/DMP, Debt Payoff, Action Plan, Veteran Benefits, Tasks, Compliance, Notes).
   **Credit disputes hand off to DisputeFox** (status syncs back). Counselor actions push to
   the member's own portal (except sensitive/internal).
4. **Development portal** -- Donor CRM (click a donor -> full record: contact, comms prefs,
   giving history, relationships, engagement, documents), Log Gift (Zeffy auto-logs; QuickBooks
   sync; IRS-correct acknowledgments), Campaigns (manage), Grants (click-in + move stage),
   Moves management, Prospect research (internal-only).
5. **Member portal** -- the existing member dashboard, signup (+ Google sign-in), pending,
   DD-214 upload, messages, courses -- restyled to the directive, wired to the Rust API. Member
   is the source of truth for their own data.
6. **LMS (full build -- Section 4).**
7. **Battle Buddy** (staff) + **Major Finance** (member) -- per the operating protocol; the
   knowledge base (already built) grounds both.
8. **Knowledge Base** -- already built (member-visible/staff-only wall); port to Rust.

---

## 4. LMS -- full build

The learning system is a first-class product, not an afterthought. Built out from the existing
`courses.py` / course pages.

- **Course catalog** -- courses with categories, thumbnails, descriptions, veteran-focused
  tracks (credit, budgeting, benefits).
- **Course structure** -- course -> modules -> lessons; lesson types: text/article, video,
  downloadable resource, quiz.
- **Learner experience** -- enroll, resume-where-you-left-off, progress %, completion,
  certificates (celebration moment per the directive), a "learning journey" map (`journey.js`).
- **Assessment** -- quizzes with pass thresholds; gate later modules on prior completion.
- **Instructor/admin tools** -- create/edit courses, modules, lessons; publish/unpublish;
  assign a course to a member or cohort; see completion analytics.
- **Ties in:** course completion feeds the ED Programs outcomes and the member's record;
  **course/LMS changes publish to the public site** (the catalog on `courses.html`) per the
  Director's push requirement. Battle Buddy can recommend the right course for a member's
  situation; Major Finance can answer from course content in the knowledge base.

---

## 5. Cross-system push (the "one system" requirement)

Actions in a portal propagate automatically:
- **Board member added** (ED Roster) -> public site board section (`about.html`) with bio/photo.
- **Staff member added** (Ops/ED) -> welcome email + login provisioning + public site Staff &
  Coaches section with bio/photo.
- **LMS change** (new/edited course) -> public course catalog on the site.
- **Compliance:** document uploaded to S3 -> fiduciary compliance calendar deadlines auto-fill.
- **Donation in Zeffy** -> auto-logged gift in the Donor CRM (+ QuickBooks sync).
- **Counselor action** -> member's own portal view (except sensitive/internal).

Each push is a backend event (Lambda) writing to the shared data + regenerating/patching the
relevant public page or record -- never manual re-entry.

---

## 6. Integrations (build vs. buy; all secrets server-side)

| Domain | Tool | Flow |
|---|---|---|
| Credit disputes | **DisputeFox** | push items -> DisputeFox; status syncs back |
| Donations | **Zeffy** | Zeffy -> auto-log gift -> Donor CRM |
| Accounting | **QuickBooks** | Development gifts -> QBO; ED financials/cash flow read from QBO |
| Documents | **S3** | upload -> compliance calendar auto-fill; DD-214 (KMS, private) |
| E-signature | **DocuSign** | consents, agreements, resolutions |
| Credit pull | bureau provider | one-click tri-bureau -> Report Analyzer / Game Plan |
| Email/SMS | Resend/SES + SMS | acknowledgments, welcome, reminders |
| Calendar | Google/Outlook | sessions, board meetings, agenda |
| AI | Battle Buddy service | `packages/battle-buddy` API contract |

---

## 7. PR plan (each PR a workable increment)

1. **Frontend shell + tokens** -- port the VAB directive three-zone shell + `shared-theme`
   tokens to vanilla (`css/` + `js/components.js` + `drawer.js`), dark-first, Inter. No behavior
   change to existing pages yet; new shell available.
2. **Backend role-access model in Rust/Lambda** -- auth, roles, the endpoint gating, `/context/current`.
3. **Port existing surfaces to the Rust API + new shell, one portal per PR** -- Member, then
   Counselor (two-level + DisputeFox), Ops, ED, Development. Each wired to real data, drawers
   not modals, Battle Buddy hooked.
4. **LMS full build** (Section 4) -- its own set of PRs.
5. **Integrations** -- DisputeFox, Zeffy, QuickBooks, DocuSign, bureau, calendar (each a PR,
   secrets via Secrets Manager).
6. **Cross-system pushes** (Section 5).
7. **AI weave** -- Battle Buddy + Major Finance presence orb, per-tool grounding, command palette.

Every PR: meets the Definition of Done (`SILENT_HONOR_OPERATING_PROTOCOL.md` Section 9), goes up
for review (PR-only, never straight to main), no secrets, no mock data in production.

---

## 8. What Tyler owns (AWS / infra)

- **AWS Secrets Manager** entries for every integration + JWT/DB, and the IAM roles that let the
  Lambdas read them.
- **Rust Lambda deploy** path + API Gateway + Terraform IaC (mirroring the VAB monorepo).
- **Data store** decision (DocumentDB vs DynamoDB) and provisioning.
- **CloudFront** (already live; security headers policy landed Jul 25) + S3 frontend bucket +
  the CI/CD pipeline (already deploys on push to main).
- Confirm the **FastAPI -> Rust migration** cutover approach (Section 11).

---

## 9. Data model (reuse + new)

- **Reuse:** `users` (roles[], pipeline stages), `disputes`, `credit_scores`, `credit_accounts`,
  `fc_data`, `documents`, `messages`, `tasks`, `course_progress`, `audit_log`, `knowledge_base`.
- **New:** `donors`, `gifts`, `campaigns`, `grants`, `board_members`, `votes`, `agenda_items`,
  `committees`, `conflicts`, `vendors`, `staff` (HR), `courses`/`modules`/`lessons` (LMS
  expansion), `context` (ACTING ON).

---

## 10. Definition of "fully workable" (the Director's bar)

- Every button is clickable and routes to the right place -- no dead ends, no placeholder
  alerts in production.
- Every create/edit opens the right slide-over drawer (not a centered modal) and saves to the
  real backend; the change appears everywhere it should (fan-out).
- Battle Buddy is wired on every surface, role-scoped, grounded in real data.
- Cross-system pushes fire (board/staff/LMS -> public site; gifts <- Zeffy; compliance <- S3).
- No secret in code; all via Secrets Manager. No mock data in production.
- Matches the VAB design directive (three-zone, drawers, dark-first, motion, AI orb).
- Fully responsive (desktop/tablet/phone), light + dark.

---

## 11. FastAPI -> Rust migration path (to confirm with Tyler)

Two options; recommend incremental:
- **Incremental (recommended):** stand up the Rust/Lambda API alongside the live FastAPI
  service; move endpoints over domain by domain behind API Gateway routing; retire FastAPI once
  parity is reached. Lower risk, keeps the site live throughout.
- **Big-bang:** rebuild the whole backend in Rust and cut over. Faster to a clean slate, higher
  risk, a hard downtime/cutover.
The knowledge-base module (just built in Python) is small enough to be an early port and a good
first proof of the Rust/Lambda + Secrets Manager pattern.

---

## 12. Decisions + open items

**Decided (Director, 2026-07-26):**
- **ProAble = the VAB Design Directive + shared-theme.** Confirmed as the UI standard.
- **Frontend = port the ProAble look to VANILLA HTML/CSS/JS.** Do NOT adopt the VAB SolidJS
  components; rebuild the three-zone shell, right drawer, tokens, Inter, motion, and AI orb in
  vanilla, reusing this repo's existing shared component system. Matches Roundtable Verdict 1
  (no framework, no build step).
- **Brand = Silent Honor keeps its own identity.** Use the directive's structure/patterns/motion,
  but Silent Honor's own red/navy/gold tokens (`css/global.css`) + its logo. It is a separate
  501(c)(3), not the bank. (VAB hexes stay reference-only.)
- **AI: Major Finance for SH members** (not Sgt. Savings) -- an intentional divergence from the
  VAB directive's external persona. Battle Buddy stays for staff.

**Still open (for Tyler / AWS):**
1. **Data store** on AWS (DocumentDB vs DynamoDB).
2. **FastAPI -> Rust migration path** (Section 11 -- incremental recommended).
3. **Secrets Manager entries + IAM roles** provisioned for each integration before that
   integration's PR lands.
