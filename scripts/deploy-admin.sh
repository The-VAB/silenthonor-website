#!/usr/bin/env bash
# Deploy the admin console SPA to production.
#
# Publishes the pre-built admin/ dist to the live frontend bucket at /admin/,
# preserves the old console as admin-legacy.html (rollback), turns admin.html
# into a redirect to /admin/, and invalidates CloudFront.
#
# Prereqs: run `npm --prefix admin-app run build` first (or use the committed
# admin/ dist), and have AWS credentials for account 802104113048.
#
# Usage:  bash scripts/deploy-admin.sh
set -euo pipefail

BUCKET="s3://silenthonor-frontend-802104113048"
DIST="E1H1ZTFC6CP7BY"   # CloudFront: silenthonorfoundation.org

cd "$(dirname "$0")/.."

if [ ! -f admin/index.html ]; then
  echo "admin/ dist not found — building..."
  npm --prefix admin-app ci
  npm --prefix admin-app run build
fi

echo "1/5  Backing up current admin.html -> admin-legacy.html"
aws s3 cp "$BUCKET/admin.html" "$BUCKET/admin-legacy.html" \
  --content-type text/html --metadata-directive REPLACE

echo "2/5  Uploading hashed assets (immutable, 1y cache)"
aws s3 sync admin/assets "$BUCKET/admin/assets" \
  --cache-control "public,max-age=31536000,immutable"

echo "3/5  Uploading SPA index.html (no-cache)"
aws s3 cp admin/index.html "$BUCKET/admin/index.html" \
  --content-type text/html --cache-control "no-cache"

echo "4/5  Installing admin.html redirect (no-cache)"
aws s3 cp admin.html "$BUCKET/admin.html" \
  --content-type text/html --cache-control "no-cache"

echo "5/5  Invalidating CloudFront"
aws cloudfront create-invalidation --distribution-id "$DIST" \
  --paths "/admin.html" "/admin/*" "/admin-legacy.html" \
  --query 'Invalidation.{Id:Id,Status:Status}' --output table

echo ""
echo "Done. New console: https://silenthonorfoundation.org/admin/"
echo "Rollback if needed: aws s3 cp $BUCKET/admin-legacy.html $BUCKET/admin.html --content-type text/html --metadata-directive REPLACE"
