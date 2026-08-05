# Operating State

Single source of truth for what's in motion under `SILENT_HONOR_OPERATING_PROTOCOL.md`.
Each module gets its own block below. Edit only your module's block to avoid tracker
merge conflicts across concurrent sessions.

---

## Admin Dashboard (`admin.html`)

- **Phase:** deployed (merged to `main`; not yet live — see Deploy Pipeline block)
- **Last sync date:** 2026-07-25
- **Owner of open questions:** Director
- **Notes:** Live in active use. Multi-role support (`roles[]`) already wired. The
  `admin.html`/`login.html` role-check inconsistency (PR #9) is merged to `main`.
  No Backend-to-Frontend Parity gaps identified beyond Battle Buddy (own block below).

## Member Portal (`login.html`, `dashboard.html`, `signup.html`)

- **Phase:** mid-PR
- **Last sync date:** 2026-07-25
- **Owner of open questions:** Tyler (needs to set `GOOGLE_CLIENT_ID`), Director (review)
- **Notes:** PR #9's `login.html` role fix is merged to `main`. Open now: PR #11
  (`feature/google-sign-in`) adds Google Sign-In to both `login.html` and
  `signup.html` — logs in an existing account of any role by verified email, or, if
  no account exists yet, carries the verified name/email into the normal signup form
  instead of erroring. Full DD-214/application vetting still required either way;
  Google never self-provisions an account. Needs a real `GOOGLE_CLIENT_ID` from
  Tyler before the button appears anywhere (currently a no-op).

## Deploy Pipeline (AWS: CodePipeline / App Runner / CloudFront)

- **Phase:** paused
- **Last sync date:** 2026-07-25
- **Owner of open questions:** Tyler (has real AWS console access) or whoever attaches
  the IAM policy drafted for the Director's CLI key (see project memory /
  `mlugenbell-deploy-ops-policy.json` in the session scratchpad)
- **Notes:** Merges to `main` do not auto-deploy — the GitHub→AWS webhook trigger
  described in `infra/aws/webhook.tf` needs a one-time manual setup step that hasn't
  been completed. `main` currently has real, ready work sitting on it undeployed: the
  Ryan Hammer photo fix, the dependency CVE bumps + login role fix (PR #9), and this
  operating protocol itself (PR #10). Decision as of 2026-07-25: keep merging PRs to
  `main` and batch the actual deploy for later rather than chasing AWS access per PR.

## Battle Buddy (staff/leadership AI copilot — ED, Ops, Financial Counselor, Development)

- **Phase:** in Design
- **Last sync date:** 2026-07-25
- **Owner of open questions:** Director
- **Notes:** Cold start per Section 4 is done — role-by-role research complete for
  four roles (Executive Director, Operations Manager, Financial/Credit Counselor,
  Fundraiser/Development Manager), written into `SILENT_HONOR_OPERATING_PROTOCOL.md`
  Sections 7.1–7.4. ED gets all four roles' capabilities; Ops gets its own + Counselor
  + Fundraiser (not ED-specific). Compliance/PII review required before anything ships.
  Next step: a first-pass Design artifact per role for the Director to iterate on —
  not yet built.

## Major Finance (member-facing financial assistant)

- **Phase:** in Design
- **Last sync date:** 2026-07-25
- **Owner of open questions:** Director
- **Notes:** New member-facing chatbot (spec in `SILENT_HONOR_OPERATING_PROTOCOL.md`
  Section 7.5), decided 2026-07-25: one assistant covering both credit and personal
  finance (not two). Lets logged-in members ask financial questions and get
  educational answers from the shared knowledge base, tailored to their pipeline
  stage. Name "Major Finance" is a placeholder, easily renamed. Highest-scrutiny
  surface in the whole system — it's the only assistant that talks to clients with no
  staff member in the loop, so the bright line (educational only, no personalized
  advice, no CROA-prohibited result guarantees, no product steering, always a one-tap
  route to a human counselor) is non-negotiable and needs legal/compliance sign-off
  before it goes anywhere near production. Not built.

## Knowledge Base (shared grounding + admin management surface)

- **Phase:** mid-PR
- **Last sync date:** 2026-07-25
- **Owner of open questions:** Director
- **Notes:** Spec in Section 7.6. **Built and open as PR #15** (`feature/knowledge-base`):
  backend router with a server-enforced member-visible/staff-only wall, admin CRUD
  gated to admin/staff/counselor, plus a "Knowledge Base" management area in the admin
  dashboard (table + filters + create/edit modal). The piece the Director specifically
  asked for ("an area where I can put the knowledge base"). Both assistants will draw
  from this; it's the first of the AI modules built since the others are only as good as
  what's in here. Not deployed (same batch-deploy hold as everything else on main).
  Future refinements noted in the PR: full revision history, formal review-before-publish.

## Meeting & Session Notes (Battle Buddy queryable memory / RAG)

- **Phase:** in Design
- **Last sync date:** 2026-07-25
- **Owner of open questions:** Director
- **Notes:** New capability the Director asked for (spec in Section 7.7). Capture meeting
  and session notes, then ask questions against them later — counselors query a member's
  past sessions, ED/fundraisers query a donor/prospect's past meetings. Partial today:
  member `intake_notes` and FC `session_notes` are stored, but there's no retrieval/RAG
  layer, no donor/prospect entity to attach fundraising notes to, and no document intake.
  Intake methods: text + document upload first; joining/recording meetings from the
  dashboard + transcription explicitly deferred (bigger build, needs consent handling).
  Architecture open question: embeddings/vector storage — DocumentDB vector search is the
  natural first look given the live stack, decide at build time. Highest-sensitivity data;
  strict role/entity scoping and source-citing answers are non-negotiable. Not built.

---

*Add a new `##` block per module. Don't rewrite another module's block except to add a
small, clearly-labeled note (e.g. flagging a breaking-change dependency) — leave the
rewrite to whoever owns that block.*
