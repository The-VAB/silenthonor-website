# Silent Honor — AWS Deployment

This directory contains the Terraform infrastructure-as-code that runs the
Silent Honor website + member portal on AWS.

## Architecture

```
                        ┌──────────────────────────────────────────┐
   Visitors ──HTTPS──▶  │ CloudFront ──▶ S3 (silenthonor-frontend)  │  static site
                        └──────────────────────────────────────────┘
                        ┌──────────────────────────────────────────┐
   Browser  ──HTTPS──▶  │ App Runner (FastAPI container from ECR)   │  API
                        │   ├─ VPC connector ─▶ DocumentDB (private)│  database
                        │   ├─ S3 (silenthonor-uploads, SSE-KMS)    │  DD-214 + docs
                        │   ├─ Secrets Manager (mongo uri, jwt, …)  │  secrets
                        │   ├─ SES  (or Resend via NAT)             │  email
                        │   └─ NAT gateway ─▶ internet (Resend)     │
                        └──────────────────────────────────────────┘
```

| Concern        | Old (Hostinger)              | New (AWS)                                   |
|----------------|------------------------------|--------------------------------------------|
| Frontend       | Static on VPS / nginx        | S3 + CloudFront                            |
| Backend        | uvicorn + systemd            | App Runner (managed container)             |
| Database       | MongoDB on VPS               | Amazon DocumentDB (managed, Mongo 5.0)     |
| DD-214 storage | Supabase / local disk        | S3 private bucket, SSE-KMS, TLS-only       |
| Email          | Resend                       | Resend (default) or Amazon SES             |
| Secrets        | `.env` file                  | AWS Secrets Manager                        |

The application code auto-selects the AWS backends from env vars, and keeps the
Supabase/Resend/local paths as fallbacks — so the same image runs locally and in AWS.

## One-time bootstrap

Terraform state lives in its own bucket (create it once):

```bash
aws s3api create-bucket --bucket silenthonor-terraform-state-802104113048 --region us-east-1
aws s3api put-bucket-versioning --bucket silenthonor-terraform-state-802104113048 \
  --versioning-configuration Status=Enabled
```

You also need a build bucket + a CodeBuild role for the image build (see below).

## Deploy sequence

```bash
cd infra/aws
terraform init
terraform apply            # creates VPC, DocumentDB, S3, ECR, Secrets, CloudFront, App Runner*

# * App Runner needs the image in ECR first. Order of operations:
#   1) terraform apply -target=aws_ecr_repository.backend   (create the repo)
#   2) build & push the image (below)
#   3) terraform apply                                       (create the rest incl. App Runner)

# Build & push the backend image (in-cloud, no local Docker):
ECR_REPO=silenthonor-backend \
BUILD_BUCKET=<your build bucket> \
CODEBUILD_ROLE=<codebuild role arn> \
  ../../scripts/aws-build-image.sh

# Deploy the frontend:
BUCKET=$(terraform output -raw frontend_bucket) \
DIST_ID=$(terraform output -raw cloudfront_distribution_id) \
  ../../scripts/aws-deploy-frontend.sh
```

Grab the endpoints:

```bash
terraform output backend_url        # App Runner API URL
terraform output cloudfront_domain  # frontend URL
```

## DNS cutover (manual, at your domain registrar)

The `silenthonorfoundation.org` domain is **not** in this AWS account's Route 53,
so DNS changes happen wherever the domain is registered:

1. **Frontend** — point `silenthonorfoundation.org` / `www` at the CloudFront
   domain (`terraform output cloudfront_domain`). Requires an ACM cert in
   `us-east-1` for the domain; set `frontend_aliases` + `acm_certificate_arn` and
   re-apply.
2. **API** — either use the App Runner default URL directly (the frontend already
   points at it), or add an App Runner custom domain `api.silenthonorfoundation.org`.
3. **SES** — add the CNAME records from `terraform output ses_dkim_tokens` to verify
   the domain, then request production access to leave the SES sandbox. Until then,
   keep `email_provider = "resend"`.

## Cost estimate (us-east-1, rough monthly)

| Resource                         | Est. / month |
|----------------------------------|--------------|
| DocumentDB `db.t3.medium` ×1     | ~$57         |
| NAT gateway (+ data)             | ~$33         |
| App Runner (1 vCPU / 2 GB)       | ~$25–50      |
| S3 + CloudFront (low traffic)    | ~$1–5        |
| KMS + Secrets Manager            | ~$2          |
| **Total**                        | **~$120–150** |

**Levers to cut cost** for a nonprofit budget:
- Drop the NAT gateway by committing to SES (via a VPC interface endpoint) instead of Resend → saves ~$33/mo.
- Use MongoDB Atlas free/shared tier instead of DocumentDB → saves ~$57/mo (set `MONGODB_URI` to the Atlas string, remove `docdb.tf`).
- App Runner scales to a low floor when idle.

Apply for [AWS nonprofit credits](https://aws.amazon.com/government-education/nonprofits/) to offset these.

## As-deployed (2026-07) — live environment

The initial live deploy was provisioned via the AWS CLI (the Terraform registry is
egress-blocked from the build environment). It matches this IaC **except** for the
network: the account was at its VPC limit (5/5) and over the EIP limit, so instead
of a fresh VPC the deploy **reused the existing `prod-vpc` and its NAT gateway**,
with dedicated, isolated `silenthonor-*` security groups (additive only — no
existing subnet/route/SG was modified). This also saved the ~$33/mo NAT cost.

DocumentDB uses the existing `prod-private-*` subnets. The App Runner VPC connector,
however, needed **two dedicated new subnets** (`silenthonor-apprunner-a/b`,
10.1.240.0/24 + 10.1.241.0/24, routed through the same NAT): App Runner's Hyperplane
ENIs failed to provision in the busy shared `prod-private` subnets (deployment failed
right after image pull, before "Provisioning instances"). Fresh dedicated subnets in
App Runner-supported AZs (use1-az1/az2) resolved it. If you rebuild, give App Runner
its own subnets rather than reusing heavily-used ones.

| Resource            | Value                                                        |
|---------------------|--------------------------------------------------------------|
| Region / Account    | us-east-1 / 802104113048                                     |
| API (App Runner)    | https://tv9nakyd9p.us-east-1.awsapprunner.com               |
| Frontend (CloudFront)| https://d27zjlncmljktr.cloudfront.net                      |
| Frontend bucket     | silenthonor-frontend-802104113048                           |
| Uploads bucket      | silenthonor-uploads-802104113048 (SSE-KMS, private, TLS-only)|
| DocumentDB          | silenthonor-docdb (db.t3.medium, 1 instance, in prod-vpc)   |
| VPC                 | vpc-08f6c3091778e46b1 (prod-vpc)                            |
| DocDB subnets       | prod-private-1a/1b/1c                                        |
| App Runner subnets  | silenthonor-apprunner-a/b (10.1.240/241.0/24) — dedicated   |
| Secrets             | silenthonor/{mongodb-uri,jwt-secret,resend-api-key,admin-password} |
| ECR                 | 802104113048.dkr.ecr.us-east-1.amazonaws.com/silenthonor-backend |
| KMS alias           | alias/silenthonor-uploads                                    |

To reproduce this as a fresh isolated VPC (once a VPC-limit increase is granted),
apply the Terraform as-is. To reuse an existing VPC instead, replace `network.tf`'s
VPC/subnet/NAT resources with `data` lookups for the target VPC and its private
subnets, and keep only the two security groups + the S3 gateway endpoint.

**Post-deploy manual steps still required:**
1. Put the real Resend API key into `silenthonor/resend-api-key` (currently a
   `REPLACE_ME` placeholder) — otherwise outbound email is disabled.
2. Add the SES DKIM CNAMEs + request SES production access if switching email to SES.
3. DNS: point `silenthonorfoundation.org` → CloudFront and (optionally)
   `api.silenthonorfoundation.org` → App Runner custom domain, at the registrar.
4. Migrate existing MongoDB data + DD-214 files (below).
5. The bootstrap admin password is in Secrets Manager (`silenthonor/admin-password`);
   log in and change it.

## Custom domains (silenthonorfoundation.org + silenthonor.org)

Canonical site = **silenthonorfoundation.org** (apex primary); **silenthonor.org**
redirects to it. Because GoDaddy DNS can't alias an apex to CloudFront, DNS for
`silenthonorfoundation.org` is delegated to **Route 53** (zone `Z0665134NU5HGJLGSP1D`).

**What you do at GoDaddy (one time):**
1. `silenthonorfoundation.org` → set nameservers to:
   ```
   ns-1055.awsdns-03.org
   ns-1925.awsdns-48.co.uk
   ns-954.awsdns-55.net
   ns-469.awsdns-58.com
   ```
2. `silenthonor.org` → add a **Domain Forwarding** rule (301) to
   `https://silenthonorfoundation.org` for both the root and `www` (leave its
   MX/email records alone). No AWS resources needed for the redirect.

Everything else is already staged in Route 53 (ACM + App Runner cert validation,
`api` → App Runner, SES DKIM). Once the nameservers propagate, ACM and the App
Runner custom domain validate automatically, then run:

```bash
CERT_ARN=<acm arn> CF_ID=<dist id> ZONE_ID=Z0665134NU5HGJLGSP1D \
SVC_ARN=<apprunner arn> FE_BUCKET=silenthonor-frontend-802104113048 \
CF_DOMAIN=d27zjlncmljktr.cloudfront.net \
  ./scripts/aws-finalize-domains.sh
```

It attaches the cert + aliases to CloudFront, points apex/www at CloudFront, and
(once `api.silenthonorfoundation.org` is active) repoints the frontend at
`https://api.silenthonorfoundation.org` — which makes auth cookies **first-party**
(same registrable domain), fixing the Safari third-party-cookie caveat. Re-runnable;
it no-ops until the cert is issued.

## Data migration

Move existing MongoDB data into DocumentDB with `mongodump`/`mongorestore`:

```bash
mongodump --uri "<old mongodb uri>" --db silenthonor --archive=sh.archive --gzip
mongorestore --uri "<docdb uri incl. tls params>" --archive=sh.archive --gzip
```

Copy DD-214 files from Supabase/local into the uploads bucket under the same
`dd214/` and `documents/` keys, then set each member's `dd214_storage_type` to `s3`.
