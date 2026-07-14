#!/bin/bash
# Finalize custom-domain cutover for Silent Honor once the ACM cert is validated.
# Safe to run repeatedly: it no-ops until the cert is ISSUED, and each step is idempotent.
#
# DNS for silenthonorfoundation.org is hosted at Cloudflare. Prereq (done once, in
# Cloudflare, all records "DNS only" / grey cloud): add the ACM + App Runner cert
# validation CNAMEs and the api CNAME. That lets ACM + App Runner validate.
#
# What it does when the cert is ready:
#   1. Attach the ACM cert + aliases (apex, www) to the CloudFront distribution
#   2. Once the App Runner custom domain is active, repoint the frontend at
#      https://api.silenthonorfoundation.org and redeploy the static site
# The apex/www -> CloudFront and api -> App Runner DNS records live in Cloudflare
# (add them there); this script does not touch DNS.
set -euo pipefail
export AWS_DEFAULT_REGION=us-east-1

DOM=silenthonorfoundation.org
CERT_ARN="${CERT_ARN:?set CERT_ARN}"
CF_ID="${CF_ID:?set CF_ID}"
SVC_ARN="${SVC_ARN:?set SVC_ARN}"
FE_BUCKET="${FE_BUCKET:?set FE_BUCKET}"
CF_DOMAIN="${CF_DOMAIN:?set CF_DOMAIN}"        # e.g. d27zjlncmljktr.cloudfront.net
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

STATUS=$(aws acm describe-certificate --certificate-arn "$CERT_ARN" --query 'Certificate.Status' --output text)
echo "ACM cert status: $STATUS"
if [ "$STATUS" != "ISSUED" ]; then
  echo "Cert not issued yet — are the ACM validation CNAMEs added in Cloudflare (DNS only)? Exiting (safe to re-run)."
  exit 0
fi

echo "=== [1/2] CloudFront: attach cert + aliases ==="
python3 - "$CF_ID" "$CERT_ARN" "$DOM" <<'PY'
import sys, json, subprocess
cf_id, cert_arn, dom = sys.argv[1:4]
cfg = json.loads(subprocess.check_output(["aws","cloudfront","get-distribution-config","--id",cf_id]))
etag = cfg["ETag"]; dc = cfg["DistributionConfig"]
aliases = [dom, f"www.{dom}"]
dc["Aliases"] = {"Quantity": len(aliases), "Items": aliases}
dc["ViewerCertificate"] = {
    "ACMCertificateArn": cert_arn, "SSLSupportMethod": "sni-only",
    "MinimumProtocolVersion": "TLSv1.2_2021", "Certificate": cert_arn,
    "CertificateSource": "acm",
}
open("/tmp/cf_cfg.json","w").write(json.dumps(dc))
subprocess.check_call(["aws","cloudfront","update-distribution","--id",cf_id,
    "--if-match",etag,"--distribution-config","file:///tmp/cf_cfg.json"],
    stdout=subprocess.DEVNULL)
print("CloudFront updated with aliases:", aliases)
PY

echo "NOTE: apex + www -> $CF_DOMAIN must exist in Cloudflare (CNAME, DNS only). This script does not manage DNS."

echo "=== [2/2] Frontend -> api.$DOM (only once App Runner domain is active) ==="
AR_STATUS=$(aws apprunner describe-custom-domains --service-arn "$SVC_ARN" \
  --query "CustomDomains[?DomainName=='api.$DOM'].Status|[0]" --output text)
echo "App Runner custom domain status: $AR_STATUS"
if [ "$AR_STATUS" = "active" ]; then
  OLDS=$(grep -rlE "https://[a-z0-9]+\.us-east-1\.awsapprunner\.com" "$ROOT" --include="*.html" --include="*.js" \
    | grep -vE '/(backend|infra|scripts|\.git)/' || true)
  for f in $OLDS; do
    sed -i -E "s#https://[a-z0-9]+\.us-east-1\.awsapprunner\.com#https://api.$DOM#g" "$f"
  done
  EX=(--exclude ".git/*" --exclude ".gitignore" --exclude ".gitconfig" --exclude "backend/*" --exclude "infra/*" --exclude "scripts/*" --exclude "frontend/*" --exclude "test_reports/*" --exclude "memory/*" --exclude "uploads/*" --exclude ".emergent/*" --exclude "*.py" --exclude "*.md" --exclude "docker-compose.yml" --exclude "nginx.conf" --exclude "serve.json" --exclude "package-lock.json" --exclude "*.pem" --exclude "*.key")
  aws s3 sync "$ROOT" "s3://$FE_BUCKET" "${EX[@]}" --exclude "*.html" --cache-control "public,max-age=604800,immutable" --delete --only-show-errors
  aws s3 sync "$ROOT" "s3://$FE_BUCKET" "${EX[@]}" --exclude "*" --include "*.html" --cache-control "no-cache,no-store,must-revalidate" --only-show-errors
  aws cloudfront create-invalidation --distribution-id "$CF_ID" --paths "/*" >/dev/null
  echo "Frontend repointed to https://api.$DOM and redeployed. Commit the changed files to git."
else
  echo "App Runner domain not active yet; leaving frontend on the *.awsapprunner.com URL. Re-run later to switch it."
fi
echo "=== finalize complete ==="
