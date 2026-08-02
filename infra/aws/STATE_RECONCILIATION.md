# Silent Honor — Terraform State Reconciliation Plan

> **COMPLETE 2026-08-02 (Option A).** Config refactor + imports + apply are all done. `terraform apply` ran clean: **Apply complete! Resources: 0 added, 20 changed, 0 destroyed.** A subsequent `terraform plan` reports **No changes** (state matches config). Post-apply health verified: DocumentDB `available` (DeletionProtection now `true`), App Runner `RUNNING`. See "Execution log & final plan" at the bottom.

**Status:** COMPLETE — reconciled and applied with human sign-off. State now tracks the live foundation and `terraform apply` is safe/idempotent.
**Author:** infra reconciliation pass, 2026-08-02.
**Account:** 802104113048 · **Region:** us-east-1 · **State:** `s3://silenthonor-terraform-state-802104113048/silenthonor/aws/terraform.tfstate`

---

## TL;DR

- **`terraform apply` is currently unsafe.** A baseline plan (no Rust) shows **52 to add, 2 to change, 0 to destroy**; with `-var enable_rust_api=true` it grows to ~64 to add. The "adds" include the **live production VPC networking, DocumentDB, App Runner, KMS key, uploads bucket, SES identity, and the app secrets** — all of which already exist and are serving production. Applying would collide with them and **mint new JWT / DocumentDB / admin passwords**, breaking the live site.
- **Root cause:** the live Silent Honor foundation was **placed by hand into the shared `prod-vpc`** (`vpc-08f6c3091778e46b1`, `10.1.0.0/16`), but `network.tf` is written to **create its own new `10.20.0.0/16` VPC**. Config and reality disagree about who owns the network.
- **Recommendation: Option A** — refactor the config to *reference* the shared VPC/subnets via `data` sources, then **import only the genuinely Silent-Honor-owned resources**. Do **not** import the shared VPC/subnets/NAT/IGW/route tables (they belong to the VAB/prod stack).
- **The "2 to change" is NOT console drift.** It is a **CRLF/LF line-ending artifact** from the Windows checkout (`core.autocrlf=true`, no `.gitattributes`). Fixed with a one-line `.gitattributes`; no infrastructure changes.
- **Correction to the original brief:** the Rust Lambda API was **only partially deployed**. The Lambda function `silenthonor-api` and HTTP API `silenthonor-http-api` **do not exist**. Only the scaffold (IAM role, SG, and DocumentDB ingress rule) exists. See §7.

---

## 1. Current state inventory (what Terraform tracks today)

`terraform state list` → **23 managed resources + 4 data sources**. Everything tracked is the **CI/CD + CloudFront + ECR + webhook** layer:

| Layer | In state |
|---|---|
| CloudFront | `aws_cloudfront_distribution.frontend`, `..._origin_access_control.frontend`, `..._response_headers_policy.security_headers` |
| CI/CD | `aws_codepipeline.deploy`, `aws_codebuild_project.deploy`, `aws_codestarconnections_connection.github`, `aws_s3_bucket.pipeline_artifacts`, IAM roles/policies `codebuild_deploy` + `codepipeline` |
| ECR | `aws_ecr_repository.backend` |
| Webhook | `aws_lambda_function.webhook_trigger` (+ url, role, role_policy), `aws_secretsmanager_secret.github_webhook` (+ version), `random_password.github_webhook` |
| Frontend bucket | `aws_s3_bucket.frontend` (bucket only — its PAB / website-config / policy are **not** tracked) |
| IAM (human) | `aws_iam_policy.silenthonor_deploy`, `aws_iam_user_policy_attachment.mlugenbell_silenthonor_deploy` |

## 2. The core mismatch: config vs. reality

`network.tf` **creates** a dedicated VPC (`var.vpc_cidr = 10.20.0.0/16`), 2 public + 2 private subnets, an IGW, a NAT gateway + EIP, public/private route tables + associations, an S3 gateway endpoint, and two SGs.

**Reality (live account):**

| Concern | Config assumes | Live truth |
|---|---|---|
| VPC | new `silenthonor-vpc` (`10.20.0.0/16`) | shared **`prod-vpc`** `vpc-08f6c3091778e46b1` (`10.1.0.0/16`), also hosting the VAB/prod + property-pulse stacks |
| DocumentDB subnets | `aws_subnet.private[*]` (new) | shared **`prod-private-*`** subnets `subnet-060bcae134dabaccf`, `subnet-0fb8e82e523f72559`, `subnet-02ccdbaa719f0c9f4` (same subnets `prod-db-subnet-group` uses) |
| App Runner connector subnets | same `aws_subnet.private[*]` | **dedicated** `silenthonor-apprunner-a/b` subnets `subnet-06e8bddabd7060b7f`, `subnet-09bce5130d93f55fc` (`10.1.240.0/24`, `10.1.241.0/24`) |
| App Runner VPC connector name | `silenthonor-vpc-connector` | **`silenthonor-vpc-connector-2`** ⚠ name is ForceNew |
| NAT / IGW / route tables | created by silenthonor | owned by the shared prod stack — **not silenthonor's to manage** |
| S3 gateway endpoint | created by silenthonor | **none exists** on prod-vpc (only an unrelated interface endpoint) |

**Conclusion:** the network is shared and prod-owned. Silent Honor consumes it; it must not try to own it. This is why **Option A** (data-source references) is correct and Option B (import the whole VPC) is wrong.

## 3. Live Silent-Honor-owned resources (unmanaged, to be imported)

All confirmed present and healthy:

- **DocumentDB** — cluster `silenthonor-docdb` (available, engine `docdb 5.0.0`, user `shadmin`, backup 7d, port 27017), instance `silenthonor-docdb-0` (`db.t3.medium`), subnet group `silenthonor-docdb-subnets`, param group `silenthonor-docdb-params` (family `docdb5.0`), SG `sg-0fdd49a442f2b1ac0` (`silenthonor-docdb-sg`). **`DeletionProtection=false`** (config wants `true` → beneficial in-place change on import). Encrypted with KMS `53aa8411-…`.
- **KMS** — key `53aa8411-56b4-4833-85bb-4d97a6f90b32` (desc "Silent Honor DD-214/document encryption") + alias `alias/silenthonor-uploads`. **This is the same key the uploads bucket uses**, so importing the key + DocumentDB together is internally consistent (no replace risk).
- **App Runner** — service `silenthonor-backend` (RUNNING, port 8000, image `…/silenthonor-backend:latest`, roles `silenthonor-apprunner-access` / `silenthonor-apprunner-instance`, health `/health`), VPC connector `silenthonor-vpc-connector-2` (SG `sg-00f6ea9d21cc6a12d`).
- **S3 uploads bucket** — `silenthonor-uploads-802104113048` (KMS-encrypted with the key above) + its PAB / SSE / versioning / TLS policy.
- **SES** — `silenthonorfoundation.org` (verified, DKIM SUCCESS).
- **Secrets Manager** — `silenthonor/jwt-secret`, `silenthonor/mongodb-uri`, `silenthonor/resend-api-key`, `silenthonor/admin-password` (the `github-webhook-secret` is already tracked).
- **Security groups** — `silenthonor-apprunner-sg` (`sg-00f6ea9d21cc6a12d`), `silenthonor-docdb-sg` (`sg-0fdd49a442f2b1ac0`).
- **IAM** — roles `silenthonor-apprunner-access` / `silenthonor-apprunner-instance` (+ inline policy + ECR attach).
- **ECR lifecycle policy** on `silenthonor-backend` (bucket/repo already tracked; lifecycle policy is not).
- **Sub-resources of already-tracked buckets** — `frontend` PAB / website-config / bucket-policy; `pipeline_artifacts` PAB / SSE.

## 4. The "2 to change" — resolved: line-ending artifact, not drift

| Resource | Diff | Cause |
|---|---|---|
| `aws_codebuild_project.deploy` | `buildspec` shows every line removed+re-added identically | `buildspec-pipeline.yml` is **CRLF** in the Windows checkout; live was set from an **LF** environment |
| `aws_lambda_function.webhook_trigger` | `source_code_hash` differs | the zip includes **CRLF** `webhook_trigger.py`; live was deployed from **LF** |

`git config core.autocrlf` = `true`, there is **no `.gitattributes`**, and both files show `^M$`. The content is byte-identical modulo EOL. **Fix:** add `.gitattributes` normalizing `*.yml`, `*.py`, `*.sh` (and buildspecs) to `eol=lf`, re-checkout, re-plan → both changes disappear. No apply needed against the live resources.

## 5. Recommended plan — Option A, in ordered phases

> Imports only write **state**, never infrastructure, so phases 0–3 are reversible (`terraform state rm`) and safe to run without an apply. **Phase 4 apply requires human sign-off.**

**Phase 0 — EOL normalization.** Add `.gitattributes`, renormalize, confirm the 2 "changes" vanish.

**Phase 1 — Config refactor (network → data sources).** In a PR:
- Replace `aws_vpc.main`, `aws_subnet.public/private`, `aws_internet_gateway.igw`, `aws_eip.nat`, `aws_nat_gateway.nat`, `aws_route_table.*` + associations, and `aws_vpc_endpoint.s3` with `data "aws_vpc"` / `data "aws_subnet"` lookups (by id or `Name` tag) — or plain `variable`s holding the known IDs.
- Point `aws_docdb_subnet_group.main.subnet_ids` at the **shared prod-private** subnets; point `aws_apprunner_vpc_connector.main.subnets` at the **dedicated silenthonor-apprunner** subnets (they are *different* sets — the current config wrongly uses one set for both).
- Set `aws_security_group.apprunner/docdb.vpc_id` to the shared VPC id.
- Rename `aws_apprunner_vpc_connector.main.vpc_connector_name` → `silenthonor-vpc-connector-2` to match live (avoids a ForceNew replace).
- Drop `aws_vpc_endpoint.s3` (no live equivalent; the shared VPC's owner manages endpoints).

**Phase 2 — Secrets, so import never overwrites live values or resets the DB password.** Recommended: remove `random_password.docdb/jwt/admin` and the generated `secret_string`/`master_password` expressions; set placeholder values with `lifecycle { ignore_changes = [secret_string] }` on the four `secret_version`s and `ignore_changes = [master_password]` on `aws_docdb_cluster.main`. Net effect after import: **0 diff**, live secret values and DB password untouched. (Alternative: `terraform import` each `random_password` with its real current value — a true 0-diff but requires handling raw secret strings; not recommended.)

**Phase 3 — Imports.** Run the import map in the Appendix (state-only).

**Phase 4 — Verify + apply (human-gated).** Re-plan until it reads **0 change** (or only the intended additive `deletion_protection true` and the harmless ECR-lifecycle text tidy). A human reviews the final plan and runs `terraform apply`.

**Phase 5 (later) — Rust API adoption.** See §7. Not part of the core reconciliation.

## 6. Risk register

| # | Risk | Mitigation |
|---|---|---|
| R1 | Apply mints new JWT/DocumentDB/admin passwords, breaking prod | Phase 2 `ignore_changes` (+ never apply pre-reconciliation) |
| R2 | DocumentDB `master_password` reset on import | `ignore_changes=[master_password]` |
| R3 | App Runner connector name ForceNew → replace (ripples to the service) | Rename config to `…-connector-2` before import |
| R4 | `docdb` SG mixes an **inline** `ingress` (App Runner) with a **standalone** `aws_vpc_security_group_ingress_rule` (Rust Lambda) — these fight in Terraform | Watch after import; likely convert the inline block to standalone rules |
| R5 | Touching the shared prod-vpc | Option A never imports shared networking |
| R6 | `deletion_protection` currently **false** on live DocumentDB | Import flips it to `true` (config) — desirable |

## 7. Correction: the Rust API is only a partial scaffold

Live check: `aws lambda get-function silenthonor-api` → **not found**; no `silenthonor-http-api`. What *does* exist: role `silenthonor-lambda-api-role` (+ `silenthonor-lambda-api-secrets` inline + `AWSLambdaVPCAccessExecutionRole`), SG `silenthonor-lambda-api-sg` (`sg-0f0845455bf75ee48`), and the `docdb-from-lambda` ingress rule on the docdb SG. So "adopting the Rust stack" means: **import the 3 existing scaffold resources**, then a future `apply -var enable_rust_api=true -var rust_api_zip_path=…` **creates** the Lambda + API Gateway (genuinely new; needs the built zip). This is additive and safe, but it is *not* the "import everything that's already there" the brief assumed.

## 8. Out-of-scope extras found (leave alone, documented)

- `s3://silenthonor-build-802104113048` — not in config (likely a Rust/CodeBuild artifact bucket). Not imported, not deleted.
- IAM role `silenthonor-codebuild` (created 2026-07-13, codebuild principal) — not in current config (config has `-codebuild-deploy` / `-codebuild-rust`). Legacy/bootstrap. Left as-is.

## Appendix — import ID map (Phase 3)

> Run after Phases 1–2 are merged. `terraform import <address> <id>`.

```
# KMS + uploads bucket
aws_kms_key.uploads                                       53aa8411-56b4-4833-85bb-4d97a6f90b32
aws_kms_alias.uploads                                     alias/silenthonor-uploads
aws_s3_bucket.uploads                                     silenthonor-uploads-802104113048
aws_s3_bucket_public_access_block.uploads                silenthonor-uploads-802104113048
aws_s3_bucket_server_side_encryption_configuration.uploads   silenthonor-uploads-802104113048
aws_s3_bucket_versioning.uploads                          silenthonor-uploads-802104113048
aws_s3_bucket_policy.uploads_tls                          silenthonor-uploads-802104113048

# frontend + pipeline-artifacts sub-resources (parent buckets already in state)
aws_s3_bucket_public_access_block.frontend               silenthonor-frontend-802104113048
aws_s3_bucket_website_configuration.frontend             silenthonor-frontend-802104113048
aws_s3_bucket_policy.frontend                            silenthonor-frontend-802104113048
aws_s3_bucket_public_access_block.pipeline_artifacts     silenthonor-pipeline-artifacts-802104113048
aws_s3_bucket_server_side_encryption_configuration.pipeline_artifacts  silenthonor-pipeline-artifacts-802104113048

# Security groups
aws_security_group.apprunner                             sg-00f6ea9d21cc6a12d
aws_security_group.docdb                                 sg-0fdd49a442f2b1ac0

# DocumentDB
aws_docdb_subnet_group.main                              silenthonor-docdb-subnets
aws_docdb_cluster_parameter_group.main                   silenthonor-docdb-params
aws_docdb_cluster.main                                   silenthonor-docdb
aws_docdb_cluster_instance.main[0]                       silenthonor-docdb-0

# App Runner
aws_apprunner_vpc_connector.main                         arn:aws:apprunner:us-east-1:802104113048:vpcconnector/silenthonor-vpc-connector-2/1/bfdd3768be9c42ffaee1b0b1d78447c5
aws_apprunner_service.backend                            arn:aws:apprunner:us-east-1:802104113048:service/silenthonor-backend/8b807105d605449b8f2240e993652766

# IAM (App Runner)
aws_iam_role.apprunner_access                            silenthonor-apprunner-access
aws_iam_role.apprunner_instance                          silenthonor-apprunner-instance
aws_iam_role_policy.apprunner_instance                   silenthonor-apprunner-instance:silenthonor-apprunner-instance-policy   # verify live inline name
aws_iam_role_policy_attachment.apprunner_ecr             silenthonor-apprunner-access/arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

# ECR lifecycle
aws_ecr_lifecycle_policy.backend                         silenthonor-backend

# SES
aws_sesv2_email_identity.domain                          silenthonorfoundation.org

# Secrets (import secret; versions imported separately — id form: <secret-arn>|<version-id or AWSCURRENT>)
aws_secretsmanager_secret.jwt                             arn:aws:secretsmanager:us-east-1:802104113048:secret:silenthonor/jwt-secret-4gbKT9
aws_secretsmanager_secret.mongodb_uri                    arn:aws:secretsmanager:us-east-1:802104113048:secret:silenthonor/mongodb-uri-EJd0Ob
aws_secretsmanager_secret.resend                         arn:aws:secretsmanager:us-east-1:802104113048:secret:silenthonor/resend-api-key-961xM0
aws_secretsmanager_secret.admin_password                arn:aws:secretsmanager:us-east-1:802104113048:secret:silenthonor/admin-password-zGj0fD

# --- Rust scaffold (only if adopting §7, with enable_rust_api=true) ---
aws_security_group.lambda_api[0]                          sg-0f0845455bf75ee48
aws_iam_role.lambda_api[0]                                silenthonor-lambda-api-role
# (role policy, VPC-access attach, and docdb_from_lambda ingress rule imported similarly)
```

### NOT imported (Option A references these; owned by the shared prod stack)
`aws_vpc.main`, `aws_subnet.public[*]`, `aws_subnet.private[*]`, `aws_internet_gateway.igw`, `aws_eip.nat`, `aws_nat_gateway.nat`, `aws_route_table.public/private` (+ associations), `aws_vpc_endpoint.s3`.

---

## Execution log & final plan (2026-08-02)

**Done (state-only + config; no `terraform apply`):**

- **Phase 0 — EOL.** Added root `.gitattributes` (LF for `infra/aws/*.{yml,yaml,tf,sh}` + `**/*.py`); renormalized `buildspec-pipeline.yml` + `lambda/webhook_trigger.py`. Resolves the 2 CRLF phantom changes.
- **Phase 1 — network refactor.** `network.tf` now only reads the shared VPC (`data.aws_vpc.shared`, var `shared_vpc_id`) and manages the two silenthonor SGs. SG `name`/`description` set to EXACTLY match live (ForceNew-safe). Removed VPC/subnets/NAT/IGW/route-tables/S3-endpoint. Subnet IDs come from `docdb_subnet_ids` (shared prod-private) and `apprunner_subnet_ids` (dedicated). App Runner connector renamed to `…-vpc-connector-2`. docdb SG ingress/egress converted to standalone rules (avoids the inline-vs-standalone conflict, R4).
- **Phase 2 — secrets.** Dropped `random_password.docdb/jwt/admin` + `local.mongodb_uri`; the 4 secret versions use a placeholder + `ignore_changes = [secret_string]`; docdb cluster `master_password` is a placeholder + `ignore_changes`. Import never rewrites a live credential or resets the DB password (verified: neither appears in the final diff).
- **Phase 3 — imports.** 35 resources imported (see appendix). `aws_s3_bucket_website_configuration.frontend` was dropped from config instead (no live equivalent — CloudFront serves via OAC/REST).
- **Reconciled drift found during import:**
  - App Runner instance IAM policy: matched config to the live policy verbatim (0-diff). The live `SecretsKmsDecrypt` statement is redundant (secrets use the AWS-managed key, no CMK) — **tightening the policy is a deliberate follow-up, not bundled here.**
  - App Runner **env drift** (real console drift): `EMAIL_PROVIDER` live=`ses` (was `resend`), `FROM_EMAIL` live uses `no-reply@`, `CORS_ORIGINS` live has full `https://` origins + the CloudFront domain `d27zjlncmljktr.cloudfront.net`. Config updated to match live (SES is verified w/ DKIM SUCCESS — live is production truth). New `var.cors_origins`.
  - docdb param-group + subnet-group descriptions and instance `promotion_tier=1` matched to live; ECR lifecycle policy description matched (`Keep last 10`). These removed 2 ForceNew replacements.

**Final `terraform plan` = 0 add, 20 change, 0 destroy.** Every change is one of:
1. `default_tags` additions (`Project`/`ManagedBy`/`Owner`) — metadata only.
2. Provider-default fields recorded in state (`recovery_window_in_days`, `revoke_rules_on_delete`, `force_destroy`, …) — no-ops on AWS.
3. **Intended** DocumentDB hardening: `deletion_protection false→true`, `+ final_snapshot_identifier`, `skip_final_snapshot true→false`, and pinning `tls=enabled` (`pending-reboot`, already the effective default → no reboot).
4. `aws_lambda_function.webhook_trigger` hash — byte-identical code (verified by diffing the live package), one-time reconciliation, stable thereafter.

Audited absent from the diff: `master_password`, `secret_string`, secret values, `kms_key_id`, SG `vpc_id`/`name`/`description`, any `forces replacement`, any destroy. App Runner service change is **tags-only** (no redeploy).

## Still open (NOT done here)

- ~~`terraform apply`~~ — **DONE** (0 added, 20 changed, 0 destroyed; post-apply plan = No changes).
- **Push / PR** — committed on branch `claude/nice-cori-a2f359` (commit `3cbb5a7` + this doc-update follow-up). Not yet pushed. The natural PR base is `feat/rust-lambda-backend` (which owns `infra/aws`) — that diff shows only the reconciliation changes.
- **Rust API adoption** (§7) — deferred. Would import the 3 scaffold resources under `-var enable_rust_api=true`, then apply to create the Lambda + HTTP API (needs the built zip).
- **Follow-ups:** tighten the App Runner instance IAM policy (drop redundant `SecretsKmsDecrypt`, use exact secret ARNs); confirm ownership intent for the two `silenthonor-apprunner-*` subnets (currently referenced, not owned); out-of-config extras left alone (`silenthonor-build` bucket, `silenthonor-codebuild` role).

---

## Follow-up updates (2026-08-02, post-reconcile)

- **#2 IAM tighten — DONE & APPLIED.** App Runner instance policy dropped the redundant `SecretsKmsDecrypt` (secrets use the AWS-managed key; `KmsKeyId=None` on all four) and scoped `ReadSecrets` to exact ARNs. `Apply complete! 0 added, 1 changed, 0 destroyed`; App Runner still `RUNNING`; live policy Sids now `UploadsObjects/UploadsList/UploadsKms/Ses/ReadSecrets`.
- **#3 apprunner subnets — DECIDED: reference-only (final).** The two `silenthonor-apprunner-*` subnets stay referenced (via `var.apprunner_subnet_ids`), not owned — silenthonor's state does not manage networking inside the shared prod-vpc. Documented in `variables.tf`.
- **#1 Rust API — DONE, ADOPTED, FIXED & HEALTHY.** The Rust API is now terraform-managed and working (`GET .../health → {"status":"ok","db":"up"}`, HTTP 200). Story:
  - A concurrent CLI deploy (via `deploy-rust-api-cli.sh`, run from Git Bash ~14:32 UTC) had created Lambda `silenthonor-api` + HTTP API `e1tyj5meuc`, but it returned **HTTP 500**.
  - **Root cause:** the CLI (Git Bash on Windows) mangled `DOCDB_CA_PATH=/var/task/global-bundle.pem` into `C:/Program Files/Git/var/task/global-bundle.pem`, so the Rust code pointed DocumentDB's TLS CA at a nonexistent path → `db connect failed`. Terraform sets that env var via the API (no shell mangling), so **adoption fixed it**.
  - Built the arm64 `bootstrap` in a `cargo-lambda` container, packaged `api.zip` (bootstrap 0755 + `global-bundle.pem`), uploaded to `s3://silenthonor-pipeline-artifacts-802104113048/rust/api.zip`.
  - Imported the full stack (5 scaffold + Lambda + API + integration + 2 routes + stage + permission) and applied the fix: `0 added, 4 changed, 0 destroyed`.
  - Cleaned up an accidental **duplicate** HTTP API (`zu33514kz3`) that a first apply created before hitting a 409 on the pre-existing Lambda.
  - **Durability:** `enable_rust_api` default flipped to `true` and the Lambda now deploys from **S3** (`rust_api_s3_bucket/key` + `rust_api_source_hash`) — a plain `terraform plan` no longer needs a local zip, and no longer wants to destroy the stack. Fixed a CORS bug (`silenthonor.org` → the real `cors_origins`). Final default-vars plan = **No changes**.
  - Redeploy new Rust code: rebuild `api.zip` → `aws s3 cp` to the bucket/key → `-var rust_api_source_hash=<new base64 sha256>` → apply.
