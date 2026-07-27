# backend-rust

The Silent Honor backend, rebuilt in Rust for AWS Lambda. See
[`docs/RUST_BACKEND.md`](../docs/RUST_BACKEND.md) for architecture, the migration
plan, and deploy steps.

## Quick start (local)

```bash
export JWT_SECRET=dev-only-change-me
export MONGODB_URI='mongodb://localhost:27017'
export MONGODB_DB=silenthonor
export COOKIE_SECURE=false
cargo run -p api        # serves http://localhost:8000
```

## Checks

```bash
cargo fmt --all
cargo clippy --all-targets -- -D warnings
cargo test
cargo build --release
```

## Implemented so far

- `POST /api/auth/login` · `GET /api/auth/me` · `POST /api/auth/logout`
- `GET /health` · `GET /api/health`

Everything else is tracked in the migration checklist in `docs/RUST_BACKEND.md`.

**No secrets in code.** `JWT_SECRET`/`MONGODB_URI` come from env locally and from
AWS Secrets Manager (by name, via the Lambda IAM role) in production.
