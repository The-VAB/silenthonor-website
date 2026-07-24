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

## Battle Buddy (AI assistant — ED, Ops Manager, Financial/Credit Counselor, Development)

- **Phase:** in Design
- **Last sync date:** 2026-07-25
- **Owner of open questions:** Director
- **Notes:** Cold start per Section 4 is done — role-by-role research complete for
  four roles (Executive Director, Operations Manager, Financial/Credit Counselor,
  Fundraiser/Development Manager), written into `SILENT_HONOR_OPERATING_PROTOCOL.md`
  Section 7. Compliance/PII review is required before anything here ships, given it
  touches member financial data and DD-214-adjacent information. Next step: a
  first-pass Design artifact per role for the Director to iterate on — not yet built.

---

*Add a new `##` block per module. Don't rewrite another module's block except to add a
small, clearly-labeled note (e.g. flagging a breaking-change dependency) — leave the
rewrite to whoever owns that block.*
