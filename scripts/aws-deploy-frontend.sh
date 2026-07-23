#!/bin/bash
# Sync the static frontend to S3 and invalidate CloudFront.
# Usage: BUCKET=<frontend-bucket> DIST_ID=<cloudfront-id> ./scripts/aws-deploy-frontend.sh
set -euo pipefail

BUCKET="${BUCKET:?set BUCKET to the frontend S3 bucket}"
DIST_ID="${DIST_ID:?set DIST_ID to the CloudFront distribution id}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Syncing static assets (long cache) ..."
# Long-lived assets
aws s3 sync "$ROOT" "s3://$BUCKET" \
  --exclude ".git/*" --exclude "backend/*" --exclude "infra/*" \
  --exclude "scripts/*" --exclude "test_reports/*" --exclude "memory/*" \
  --exclude "*.py" --exclude "*.md" --exclude "docker-compose.yml" \
  --exclude "*.html" \
  --cache-control "public,max-age=604800,immutable" \
  --delete

echo "Syncing HTML (no cache) ..."
aws s3 sync "$ROOT" "s3://$BUCKET" \
  --exclude "*" --include "*.html" \
  --cache-control "no-cache,no-store,must-revalidate"

echo "Invalidating CloudFront ..."
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" >/dev/null

echo "Frontend deployed to bucket $BUCKET and CloudFront $DIST_ID invalidated."
