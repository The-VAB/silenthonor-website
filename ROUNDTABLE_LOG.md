# Roundtable Log

Running ledger of every Roundtable verdict, appended in order. Never edit past
entries except to fill in **Revisit outcome** once a revisit date arrives. Each new
Roundtable run checks this file first for past revisit dates that passed with no
outcome recorded.

Entry format:

```markdown
### Verdict N — <YYYY-MM-DD>

- **Decision:** <one line>
- **Facts checked:** <verified/corrected, or "none — no checkable claims">
- **Where it agreed:** <one line>
- **Where it clashed:** <vote, e.g. "3-of-5 favor A">
- **Blind spots caught:** <one line>
- **Final call:** <recommendation + Monday-morning action + owner>
- **Revisit by:** <date>
- **Revisit outcome:** pending
```

---

<!-- Verdicts are appended below this line. -->

### Verdict 1 — 2026-07-25

- **Decision:** Full frontend rewrite (vanilla HTML/CSS/JS → component framework, e.g. React/Next.js) for silenthonor-website, motivated by anticipated traffic/scale and better front+back security.
- **Facts checked:** Confirmed — 35 hand-authored static HTML pages, zero framework/build tooling anywhere; frontend on S3+CloudFront (already globally edge-cached); backend FastAPI/App Runner + DocumentDB; real veteran PII in scope (credit repair, DD-214 uploads). Confirmed first-hand (this session): a dashboard-widget CSS/JS duplication bug drifted out of sync across separate PRs; a backend dependency security pass (Dependabot-driven) was just completed; a working CI/CD pipeline (CodePipeline+CodeBuild, GitHub webhook) now deploys on push to main. **Corrected/new finding:** production CloudFront currently ships with **zero security headers** (no CSP/HSTS/X-Frame-Options/X-Content-Type-Options) — the only X-Frame-Options in the repo is in a dev-only nginx.conf never used in prod. Unverifiable directly: team size/engineering capacity (no org-chart access), but consistent with all observed evidence.
- **Where it agreed:** All 6 seats independently flagged the same immediate action regardless of the framework verdict — ship a CloudFront Response Headers Policy now, since it's a config-only fix orthogonal to frontend stack. All agreed the stated "traffic/scale" motivation doesn't hold (static+CDN already scales well; a rewrite could add scaling surface, not remove it, if it introduces SSR). All agreed the real maintainability pain (widget CSS/JS duplication) doesn't require full framework adoption — a lightweight partials/includes fix addresses it directly.
- **Where it clashed:** 5-of-6 (Contrarian, First-Principles, Outsider, Executor, Security) against doing the full rewrite now. 1-of-6 (Expansionist) in favor, but scoped down to an incremental page-by-page migration behind the existing CI/CD rather than a big-bang rewrite, and still agreeing the headers fix should land immediately/alongside.
- **Blind spots caught:** Security seat surfaced a concrete, actionable item none of the others named specifically — audit the 35 pages for unsafe DOM sinks (`innerHTML`/`document.write` with unsanitized input) rather than assuming a framework's auto-escaping is needed. Security and Contrarian both flagged the irony that a framework rewrite would introduce a large new npm supply-chain attack surface right after the team just finished disciplined backend dependency hardening. Expansionist's dissent named a real consideration the majority underweighted: framework conventions lower the onboarding cost for the intermittent volunteer/contributor engineering a small nonprofit relies on — doesn't overturn the verdict, but is a legitimate factor for a future revisit.
- **Final call:** Don't do the full frontend rewrite now. (1) Ship a CloudFront Response Headers Policy (CSP, HSTS, X-Frame-Options, X-Content-Type-Options) — highest-leverage, lowest-risk, hours of work, owner: whoever holds AWS/infra access per CLAUDE.md's allowed list (mlugenbell/ttorres), by **2026-08-01**. (2) Extract the duplicated dashboard-widget CSS/JS into shared includes/partials (no build step required) — no fixed deadline, before the next PR that touches it. (3) Audit existing pages for unsafe DOM sinks and review FastAPI auth/session/upload-validation logic directly, as the real security follow-up. Revisit the framework question only if a specific, measured traffic or maintainability problem emerges that these fixes don't solve.
- **Revisit by:** 2026-09-01
- **Revisit outcome:** pending
