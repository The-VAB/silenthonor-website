#!/bin/bash
# Build & push the backend image to ECR using AWS CodeBuild (no local Docker).
# Zips the repo, uploads to S3, runs a CodeBuild project, and waits for it.
#
# Requires (created by Terraform / bootstrap):
#   ECR_REPO       - ECR repository name (e.g. silenthonor-backend)
#   BUILD_BUCKET   - an S3 bucket to hold the source zip + artifacts
#   CODEBUILD_ROLE - IAM role ARN CodeBuild assumes (ECR push + logs + S3 read)
# Optional: IMAGE_TAG (default: latest), AWS_DEFAULT_REGION (default: us-east-1)
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
PROJECT="silenthonor-image-build"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

: "${ECR_REPO:?set ECR_REPO}"
: "${BUILD_BUCKET:?set BUILD_BUCKET}"
: "${CODEBUILD_ROLE:?set CODEBUILD_ROLE}"

echo "Packaging source..."
ZIP="/tmp/silenthonor-src-$$.zip"
( cd "$ROOT" && zip -qr "$ZIP" backend infra/aws/buildspec.yml )
aws s3 cp "$ZIP" "s3://$BUILD_BUCKET/source.zip" --region "$REGION"
rm -f "$ZIP"

ENV_VARS=$(cat <<JSON
[
  {"name":"AWS_ACCOUNT_ID","value":"$ACCOUNT_ID"},
  {"name":"ECR_REPO","value":"$ECR_REPO"},
  {"name":"IMAGE_TAG","value":"$IMAGE_TAG"}
]
JSON
)

if ! aws codebuild batch-get-projects --names "$PROJECT" --region "$REGION" \
      --query 'projects[0].name' --output text 2>/dev/null | grep -q "$PROJECT"; then
  echo "Creating CodeBuild project $PROJECT..."
  aws codebuild create-project --region "$REGION" \
    --name "$PROJECT" \
    --source "{\"type\":\"S3\",\"location\":\"$BUILD_BUCKET/source.zip\",\"buildspec\":\"infra/aws/buildspec.yml\"}" \
    --artifacts '{"type":"NO_ARTIFACTS"}' \
    --environment "{\"type\":\"LINUX_CONTAINER\",\"image\":\"aws/codebuild/amazonlinux2-x86_64-standard:5.0\",\"computeType\":\"BUILD_GENERAL1_SMALL\",\"privilegedMode\":true}" \
    --service-role "$CODEBUILD_ROLE" >/dev/null
fi

echo "Starting build..."
BUILD_ID="$(aws codebuild start-build --region "$REGION" \
  --project-name "$PROJECT" \
  --environment-variables-override "$ENV_VARS" \
  --query 'build.id' --output text)"
echo "Build: $BUILD_ID"

echo "Waiting for build to finish..."
while true; do
  STATUS="$(aws codebuild batch-get-builds --ids "$BUILD_ID" --region "$REGION" \
    --query 'builds[0].buildStatus' --output text)"
  echo "  status: $STATUS"
  case "$STATUS" in
    SUCCEEDED) echo "Image pushed: $ECR_REPO:$IMAGE_TAG"; exit 0 ;;
    FAILED|FAULT|STOPPED|TIMED_OUT) echo "Build failed: $STATUS"; exit 1 ;;
  esac
  sleep 15
done
