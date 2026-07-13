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

## Data migration

Move existing MongoDB data into DocumentDB with `mongodump`/`mongorestore`:

```bash
mongodump --uri "<old mongodb uri>" --db silenthonor --archive=sh.archive --gzip
mongorestore --uri "<docdb uri incl. tls params>" --archive=sh.archive --gzip
```

Copy DD-214 files from Supabase/local into the uploads bucket under the same
`dd214/` and `documents/` keys, then set each member's `dd214_storage_type` to `s3`.
