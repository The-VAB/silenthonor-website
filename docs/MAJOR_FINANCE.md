# Major Finance (member AI) -- built, dormant, do NOT enable yet

Major Finance is the member-facing AI money assistant. The code is written and
committed, but it is **off** on purpose. Members do not see it and it answers
nothing until every condition below is met. This is deliberate: a chat tab that
cannot answer is worse than no tab.

## How the gate works

- **Backend** (`backend-rust/crates/api/src/routes/major_finance.rs`)
  - `GET /api/member/major-finance/status` returns `{ "enabled": false }` until
    the flag is turned on.
  - `POST /api/member/major-finance` refuses with "not available yet" while the
    flag is off. When on, it calls the Anthropic Messages API over HTTPS.
- **Frontend** (`major-finance.html` + the gated nav tab) polls the status
  endpoint. While `enabled` is false, the tab stays hidden and the page shows a
  "coming soon" state. It flips on automatically once the backend reports
  enabled -- no frontend change needed to launch.

So flipping one flag on the backend is what launches it, and nothing launches by
accident.

## Conditions that must ALL be true before enabling

1. **The Rust backend compiles and deploys.** The Major Finance code builds
   green in CodeBuild (or CI) and the Lambda is live. See
   [RUST_BACKEND.md](RUST_BACKEND.md).
2. **An Anthropic API key exists in Secrets Manager**, not in code. Create the
   secret (e.g. `silenthonor/anthropic-api-key`) and grant the Lambda role
   `secretsmanager:GetSecretValue` on it. The Terraform stub is in
   `infra/aws/major-finance.tf` (add the key value out of band; never commit it).
3. **The model and cost are chosen deliberately.** `MAJOR_FINANCE_MODEL`
   defaults to `claude-opus-5` (highest quality). For a high-volume member
   chatbot on a nonprofit budget, `claude-sonnet-5` or `claude-haiku-4-5` cost
   far less per message. Pick one and set the env var. This is a money decision,
   so it is Mike/Tyler's call, not a default.
4. **The guardrails are reviewed.** Read the `MF_SYSTEM` prompt in
   `major_finance.rs`: general education only, no personalized advice, no promise
   about a member's credit, defer specifics to the counselor, never collect SSNs
   or account numbers. Confirm it matches how you want the foundation to sound.
5. **Rate/cost limits are in place.** Decide a per-member or daily message cap so
   a runaway conversation can't run up the Anthropic bill. (Not yet built -- add
   before launch, or accept the risk knowingly.)
6. **A knowledge base is loaded (recommended, not required).** Today Major
   Finance answers from the model plus the system prompt only. To ground it in
   Silent Honor's own courses and policies, add retrieval before launch. Until
   then it is a general educator, which is honest but not foundation-specific.

## To enable (once all conditions are met)

Set on the Lambda (via Terraform env vars):

```
MAJOR_FINANCE_ENABLED = true
MAJOR_FINANCE_MODEL   = claude-opus-5   # or claude-sonnet-5 / claude-haiku-4-5
ANTHROPIC_API_KEY_SECRET_NAME = silenthonor/anthropic-api-key
```

Redeploy. The status endpoint starts returning `enabled: true`, the member tab
appears, and the chat works. To turn it back off, set the flag to false and
redeploy -- the tab disappears again.

## Local dev

```
export MAJOR_FINANCE_ENABLED=true
export ANTHROPIC_API_KEY=sk-ant-...      # dev only; never commit
export MAJOR_FINANCE_MODEL=claude-haiku-4-5   # cheap for testing
```
