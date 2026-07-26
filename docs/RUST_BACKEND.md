# Silent Honor — Rust / AWS Lambda backend

The real, from-scratch backend. Rust, running on AWS Lambda behind API Gateway
(HTTP API), talking to the existing Amazon DocumentDB (MongoDB-compatible)
cluster. It is being stood up **alongside** the current Python/FastAPI service and
cut over endpoint-by-endpoint (strangler migration) so the live site never breaks.

> **Security invariant.** No secret value lives in this repo or in the Lambda's
> plaintext environment. The JWT signing key and the DocumentDB connection string
> are read at cold start from **AWS Secrets Manager** via the Lambda's IAM role.
> If any future task appears to need a secret in code, stop and flag it.

---

## Layout

```
backend-rust/
  Cargo.toml                 workspace (release profile tuned for small/fast Lambda)
  rust-toolchain.toml        pinned toolchain + arm64 target
  crates/
    sh-core/                 shared library
      config.rs              load config; resolve secrets by name; CA-path rewrite
      secrets.rs             AWS Secrets Manager fetch + warm-container cache
      db.rs                  DocumentDB connection (mongodb driver, TLS from URI)
      models.rs              User (+ public profile); mirrors existing documents
      auth.rs                JWT (HS256) + bcrypt — token/hash compatible w/ Python
      error.rs               AppError -> `{ "detail": "..." }` (matches FastAPI)
    api/                     the Lambda binary (`bootstrap`)
      main.rs                cold start -> config -> DB -> axum router; Lambda or local
      state.rs               AppState { db, config }
      routes/                auth.rs, health.rs, mod.rs (router + cookie helpers)
infra/aws/lambda-api.tf      Lambda + API Gateway + VPC/IAM (inert until enabled)
.github/workflows/rust-backend.yml   compile/lint/test gate
```

## Why these choices

- **One Lambda, axum router** (`lambda_http::run(app)`). Same code runs locally as
  a plain axum server (`cargo run`) and in Lambda — one binary, real routing,
  cheap. Cold start with `provided.al2023` + arm64 is ~15–30 ms for Rust.
- **Keep DocumentDB.** The data already lives there and both services share it
  during migration. The Rust `mongodb` driver speaks the same wire protocol.
- **Cookies/JWT identical to Python** (`access_token`/`refresh_token`, HttpOnly,
  Secure, SameSite=None, HS256, bcrypt). A session minted by one backend is valid
  on the other, so cutover is seamless and reversible.

## TLS / CA bundle

DocumentDB requires TLS. The connection string in Secrets Manager was written for
App Runner (`tlsCAFile=/app/rds-global-bundle.pem`). In Lambda the package unzips
to `/var/task`, so:

1. Download Amazon's CA bundle `global-bundle.pem` and place it at the **root of
   the Lambda zip** (ends up at `/var/task/global-bundle.pem`).
2. Terraform sets `DOCDB_CA_PATH=/var/task/global-bundle.pem`; `config.rs` rewrites
   the URI's `tlsCAFile` to that path at startup (unit-tested). The secret is never
   duplicated.

## Deploy (Tyler)

Prereqs: `cargo lambda` (`cargo install cargo-lambda`), AWS creds, Terraform.

```bash
cd backend-rust
cargo lambda build --release --arm64
# package: bootstrap + CA bundle at the zip root
cp /path/to/global-bundle.pem target/lambda/bootstrap/global-bundle.pem
( cd target/lambda/bootstrap && zip -r ../../../api.zip bootstrap global-bundle.pem )

cd ../infra/aws
terraform apply \
  -var enable_rust_api=true \
  -var rust_api_zip_path=../../backend-rust/api.zip
# -> output rust_api_endpoint
```

Then point a **staging** copy of the frontend's `window.API_BASE` at that endpoint,
smoke-test login/dashboard, and only then flip production DNS/config. Everything is
reversible — the App Runner service stays up the whole time.

## Local dev

```bash
cd backend-rust
export JWT_SECRET=dev-only-change-me
export MONGODB_URI='mongodb://localhost:27017'
export MONGODB_DB=silenthonor
export COOKIE_SECURE=false
cargo run -p api           # http://localhost:8000
```

## Migration checklist — 168 endpoints across 13 routers

Port one router per PR. Each porting PR: implement handlers in `api/routes/`, add
the route to `routes/mod.rs`, keep paths/response shapes identical, verify against
the Python behavior, tick the box.

- [x] **auth** — `login`, `me`, `logout` (this PR). _Follow-up:_ `register`,
      `refresh`, `forgot-password`, `reset-password`, `change-password`,
      brute-force lockout, audit logging.
- [ ] **members** — dashboard, programs, courses, counselor, dd214 upload, profile
- [ ] **credit** — history, stats, score log (per-bureau)
- [ ] **disputes** — CRUD + status
- [ ] **courses** — catalog, detail, progress, waitlist
- [ ] **content** — announcements, pages
- [ ] **counselor** — caseload, member detail, tasks, waitlist claim
- [ ] **financial_counseling** — fc_data, game plan, budget, payoff
- [ ] **programs** — enrollment/pipeline
- [ ] **messages** — threads, send
- [ ] **staff** — add/list/deactivate, welcome email + login provisioning
- [ ] **admin** — course builder (courses/lessons), announcements, contacts, reports, audit
- [ ] **reports** — analytics rollups

Shared work still to port: request-logging + audit middleware, brute-force
`login_attempts`, S3 storage (DD-214 AES-256), SES email, input validators.

## Where the two just-approved features land

- **Financial-intake pre-verification state.** Backed by the `verified` +
  `pipeline_stage` + `dd214_status` fields, which `login`/`me` already return (see
  `models.rs::to_profile`). When **members** is ported, `register` sets
  `pipeline_stage = "applied"`, `dd214_status = "pending"`; the frontend routes
  unverified users to the pending/DD-214 state (matches `pending.html`). No new
  data model needed — the fields exist.
- **Counselor debt-payoff opens with no strategy pre-selected.** Frontend-only, in
  the counselor payoff tool — belongs in the **frontend** PR track (the prototype's
  `setStrat` default), not the API. Tracked here so it isn't lost.

## CI

`.github/workflows/rust-backend.yml` builds + tests on every PR touching
`backend-rust/`. It is authoritative — the code is authored without a local Rust
toolchain, so a green build there is the compile proof. `fmt`/`clippy` start
advisory; tighten to blocking once the tree is clean.
