# Operating State

Single source of truth for what's in motion under `SILENT_HONOR_OPERATING_PROTOCOL.md`.
Each module gets its own block below. Edit only your module's block to avoid tracker
merge conflicts across concurrent sessions.

---

## Admin Dashboard (`admin.html`)

- **Phase:** mid-PR
- **Last sync date:** 2026-07-24
- **Owner of open questions:** Director
- **Notes:** Live and in active use. Multi-role support (`roles[]`) already wired.
  A role-check inconsistency between `admin.html` and `login.html` was found and fixed
  on branch `security/dependency-bumps-and-login-role-fix` (open PR as of 2026-07-24) —
  see that PR for details. No Backend-to-Frontend Parity gaps identified yet beyond
  Battle Buddy (see its own block below).

## Member Portal (`login.html`, `dashboard.html`, `signup.html`)

- **Phase:** mid-PR
- **Last sync date:** 2026-07-24
- **Owner of open questions:** Director
- **Notes:** Same PR as Admin Dashboard above — `login.html`'s post-login/on-load
  redirect logic only checked the old singular `role` field; fixed to check `roles[]`
  with a fallback, matching `admin.html`.

## Deploy Pipeline (AWS: CodePipeline / App Runner / CloudFront)

- **Phase:** paused
- **Last sync date:** 2026-07-24
- **Owner of open questions:** whoever has full AWS console access (see
  `infra/aws/README.md` for the technical detail)
- **Notes:** Merges to `main` do not currently auto-deploy — the GitHub→AWS webhook
  trigger described in `infra/aws/webhook.tf` needs a one-time manual setup step that
  hasn't been completed. Paused here (not a code module) until someone with real AWS
  access either completes that setup or manually triggers a deploy. Not blocking PR work
  in the meantime — it only blocks changes from reaching the live site once merged.

## Battle Buddy (AI assistant — counselors + leadership)

- **Phase:** audited
- **Last sync date:** 2026-07-24
- **Owner of open questions:** Director
- **Notes:** Cold start per Section 4 of the operating protocol — nothing built yet.
  Spec lives in `SILENT_HONOR_OPERATING_PROTOCOL.md` Section 7 (the Battle Buddy
  Standard): role-aware assistant for counselors (casework support) and leadership
  (org-ops support), grounded in Silent Honor's own knowledge (courses, financial-
  counseling tools, program policy), scoped per the existing `roles[]` system.
  Compliance/PII review is required before anything here ships, given it touches
  member financial data and DD-214-adjacent information. Next step is a first-pass
  Design artifact for the Director to iterate on — not yet started.

---

*Add a new `##` block per module. Don't rewrite another module's block except to add a
small, clearly-labeled note (e.g. flagging a breaking-change dependency) — leave the
rewrite to whoever owns that block.*
