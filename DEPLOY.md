# Silent Honor Foundation — Deployment

> **The live system runs on AWS** (account `802104113048`, `us-east-1`).
> The old Hostinger VPS (`srv1077820.hstgr.cloud`) is **RETIRED** — do not deploy to it.
> Its deploy scripts were removed in this commit precisely so nobody ships there by mistake.

## Live architecture (verified 2026-07-14)

| Piece | Resource | URL / ID |
|---|---|---|
| Site (public) | CloudFront + S3 | **https://silenthonorfoundation.org** (+ `www`) |
| CloudFront distro | `E1H1ZTFC6CP7BY` | `d27zjlncmljktr.cloudfront.net` |
| Frontend bucket | S3 | `silenthonor-frontend-802104113048` |
| API | App Runner `silenthonor-backend` | `https://tv9nakyd9p.us-east-1.awsapprunner.com` |
| Database | DocumentDB | `silenthonor-docdb` (in `prod-vpc`) |
| Uploads (DD-214) | S3, SSE-KMS, private, TLS-only | `silenthonor-uploads-802104113048` |
| Email | Resend (or SES) | `noreply@silenthonorfoundation.org` |
| Secrets | Secrets Manager | `silenthonor/jwt-secret`, `/admin-password`, `/mongodb-uri`, `/resend-api-key` |
| DNS | Cloudflare | zone `silenthonorfoundation.org` (NS: `owen`/`sue.ns.cloudflare.com`) |
| TLS | ACM (us-east-1) | covers apex + `www` |

Infrastructure as code lives in [`infra/aws/`](infra/aws/) (Terraform). See its README for
the full resource map and cost notes.

## Deploy the frontend (static site)

The site is plain HTML/CSS/JS — no build step. Sync to S3 and invalidate CloudFront:

```bash
scripts/aws-deploy-frontend.sh
# or manually:
aws s3 sync . s3://silenthonor-frontend-802104113048 \
  --exclude ".git/*" --exclude "backend/*" --exclude "infra/*" --exclude "memory/*" \
  --exclude "scripts/*" --exclude "test_reports/*" --delete
aws cloudfront create-invalidation --distribution-id E1H1ZTFC6CP7BY --paths "/*"
```

`index.html` and other HTML must not be long-cached — CloudFront is configured to
revalidate HTML so deploys are visible immediately.

## Deploy the backend (API)

Build the image, push to ECR, and App Runner rolls it out:

```bash
scripts/aws-build-image.sh          # builds + pushes to ECR via CodeBuild
```

App Runner auto-deploys the new image tag. Watch it:

```bash
aws apprunner list-operations --region us-east-1 \
  --service-arn "$(aws apprunner list-services --region us-east-1 \
    --query "ServiceSummaryList[?ServiceName=='silenthonor-backend'].ServiceArn" --output text)"
```

## Configuration

Backend config is injected by App Runner — plain values as env vars, secrets from
Secrets Manager. See [`backend/.env.example`](backend/.env.example) for every variable
the code reads. Two that matter and are easy to get wrong:

- **`FRONTEND_URL`** — used to build links in outbound email (password reset). Must be
  the public site URL (`https://silenthonorfoundation.org`), *not* the CloudFront domain.
- **`CORS_ORIGINS`** — only *adds* origins. The production domains and localhost are
  always allowed in code, so a bad env value can't lock the live site out of the API.

## Verify a deploy

```bash
curl -s https://silenthonorfoundation.org -o /dev/null -w "site %{http_code}\n"
curl -s https://tv9nakyd9p.us-east-1.awsapprunner.com/api/health
# CORS must echo the site origin back:
curl -s -D- -o /dev/null -H "Origin: https://silenthonorfoundation.org" \
  https://tv9nakyd9p.us-east-1.awsapprunner.com/api/health | grep -i access-control-allow-origin
```

Then in a browser: load the site, sign up, log in, confirm the dashboard renders and the
auth cookie is set (DevTools → Application → Cookies). Auth cookies are
`HttpOnly; Secure; SameSite=None` because the site and API are on different origins.

## Local development

```bash
cp backend/.env.example backend/.env   # fill values
docker compose up --build              # frontend :3000, backend :8000, mongo :27017
```

## Security notes

- DD-214s are federal records: they go to the private, KMS-encrypted S3 bucket. Never
  expose that bucket publicly and never commit uploads.
- `ENVIRONMENT=production` suppresses writing the dev `memory/test_credentials.md` file.
  That file previously leaked an admin password into this public repo — it is now
  untracked and gitignored. Do not re-add it.
- Rotate `silenthonor/admin-password` in Secrets Manager rather than hardcoding an admin
  password anywhere.
