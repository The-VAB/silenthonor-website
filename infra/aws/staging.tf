# ─────────────────────────────────────────────────────────────────────────────
# STAGING environment (frontend + backend), mirroring prod but fully separate.
#
#   Frontend : silenthonor-staging-frontend S3 bucket + its own CloudFront dist.
#   Backend  : silenthonor-staging-api Lambda + its own HTTP API, same shared VPC
#              + secrets, MONGODB_DB=silenthonor_staging on the SHARED DocumentDB
#              cluster (isolation by database name, not a separate cluster).
#   AI       : Major Finance + Admin Assistant ENABLED in staging (off in prod).
#
# Inert by default (enable_staging=false). Stand it up with:
#   terraform apply -var enable_staging=true
#
# Custom domain (staging.silenthonorfoundation.org) is two-phase because DNS is
# on Cloudflare (not Route 53):
#   1. apply -> `terraform output staging_acm_validation` -> add that CNAME in
#      Cloudflare; the ACM cert then validates (a few minutes).
#   2. apply -var enable_staging=true -var staging_use_custom_domain=true, then
#      add a Cloudflare CNAME: staging -> `terraform output staging_cloudfront_domain`.
# Until step 2 the site serves from the CloudFront default *.cloudfront.net URL.
# ─────────────────────────────────────────────────────────────────────────────

variable "enable_staging" {
  description = "Provision the full staging environment (frontend + backend)."
  type        = bool
  default     = false
}

variable "staging_use_custom_domain" {
  description = "Attach staging.silenthonorfoundation.org to the staging CloudFront (only after the ACM cert has validated via Cloudflare DNS)."
  type        = bool
  default     = false
}

variable "staging_domain" {
  description = "Custom domain for the staging frontend."
  type        = string
  default     = "staging.silenthonorfoundation.org"
}

locals {
  stg        = var.enable_staging ? 1 : 0
  stg_custom = (var.enable_staging && var.staging_use_custom_domain) ? 1 : 0
}

# ── ACM cert for the staging domain (us-east-1, required for CloudFront) ──────
resource "aws_acm_certificate" "staging" {
  count             = local.stg
  domain_name       = var.staging_domain
  validation_method = "DNS"
  lifecycle {
    create_before_destroy = true
  }
  tags = { Name = "${var.project}-staging" }
}

# ── Frontend: private S3 bucket behind CloudFront ────────────────────────────
resource "aws_s3_bucket" "frontend_staging" {
  count  = local.stg
  bucket = "${var.project}-staging-frontend-${var.account_id}"
  tags   = { Name = "${var.project}-staging-frontend" }
}

resource "aws_s3_bucket_public_access_block" "frontend_staging" {
  count                   = local.stg
  bucket                  = aws_s3_bucket.frontend_staging[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "frontend_staging" {
  count                             = local.stg
  name                              = "${var.project}-staging-frontend-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "frontend_staging" {
  count               = local.stg
  enabled             = true
  default_root_object = "index.html"
  comment             = "Silent Honor STAGING frontend"
  aliases             = local.stg_custom == 1 ? [var.staging_domain] : []

  origin {
    domain_name              = aws_s3_bucket.frontend_staging[0].bucket_regional_domain_name
    origin_id                = "frontend-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend_staging[0].id
  }

  default_cache_behavior {
    target_origin_id           = "frontend-s3"
    viewer_protocol_policy      = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = "658327ea-f89d-4fab-a63d-7e88639e58f6" # AWS Managed-CachingOptimized
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security_headers.id
  }

  # SPA-style: serve index.html for unknown paths (harmless for the static site).
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  dynamic "viewer_certificate" {
    for_each = local.stg_custom == 1 ? [1] : []
    content {
      acm_certificate_arn      = aws_acm_certificate.staging[0].arn
      ssl_support_method       = "sni-only"
      minimum_protocol_version = "TLSv1.2_2021"
    }
  }
  dynamic "viewer_certificate" {
    for_each = local.stg_custom == 0 ? [1] : []
    content {
      cloudfront_default_certificate = true
    }
  }

  tags = { Name = "${var.project}-staging-frontend" }
}

resource "aws_s3_bucket_policy" "frontend_staging" {
  count  = local.stg
  bucket = aws_s3_bucket.frontend_staging[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontRead"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.frontend_staging[0].arn}/*"
      Condition = {
        StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.frontend_staging[0].arn }
      }
    }]
  })
}

# ── Backend: staging Lambda + HTTP API (shares VPC, secrets, DocumentDB) ──────
resource "aws_security_group" "lambda_api_staging" {
  count       = local.stg
  name        = "${var.project}-staging-lambda-api-sg"
  description = "Staging Rust API Lambda ENIs"
  vpc_id      = data.aws_vpc.shared.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.project}-staging-lambda-api-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "docdb_from_lambda_staging" {
  count                        = local.stg
  security_group_id            = aws_security_group.docdb.id
  referenced_security_group_id = aws_security_group.lambda_api_staging[0].id
  from_port                    = 27017
  to_port                      = 27017
  ip_protocol                  = "tcp"
  description                  = "Mongo/DocumentDB from STAGING Rust API Lambda"
}

resource "aws_iam_role" "lambda_api_staging" {
  count = local.stg
  name  = "${var.project}-staging-lambda-api-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_vpc_staging" {
  count      = local.stg
  role       = aws_iam_role.lambda_api_staging[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

data "aws_iam_policy_document" "lambda_secrets_staging" {
  count = local.stg
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.jwt.arn, aws_secretsmanager_secret.mongodb_uri.arn]
  }
  statement {
    sid       = "SendEmail"
    actions   = ["ses:SendEmail", "ses:SendRawEmail"]
    resources = ["*"]
  }
  statement {
    sid       = "UploadsBucket"
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${aws_s3_bucket.uploads.arn}/*"]
  }
  statement {
    sid       = "UploadsKms"
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"]
    resources = [aws_kms_key.uploads.arn]
  }
  statement {
    sid       = "BedrockInvoke"
    actions   = ["bedrock:InvokeModel"]
    resources = ["arn:aws:bedrock:*::foundation-model/anthropic.*", "arn:aws:bedrock:*:*:inference-profile/*"]
  }
}

resource "aws_iam_role_policy" "lambda_secrets_staging" {
  count  = local.stg
  name   = "${var.project}-staging-lambda-api-secrets"
  role   = aws_iam_role.lambda_api_staging[0].id
  policy = data.aws_iam_policy_document.lambda_secrets_staging[0].json
}

resource "aws_lambda_function" "api_staging" {
  count            = local.stg
  function_name    = "${var.project}-staging-api"
  role             = aws_iam_role.lambda_api_staging[0].arn
  runtime          = "provided.al2023"
  handler          = "bootstrap"
  architectures    = ["arm64"]
  s3_bucket        = var.rust_api_s3_bucket
  s3_key           = var.rust_api_s3_key
  source_code_hash = var.rust_api_source_hash
  memory_size      = var.rust_api_memory_mb
  timeout          = var.rust_api_timeout_s

  vpc_config {
    subnet_ids         = var.docdb_subnet_ids
    security_group_ids = [aws_security_group.lambda_api_staging[0].id]
  }

  environment {
    variables = {
      JWT_SECRET_NAME         = aws_secretsmanager_secret.jwt.name
      MONGODB_URI_SECRET_NAME = aws_secretsmanager_secret.mongodb_uri.name
      MONGODB_DB              = "${var.project}_staging"
      DOCDB_CA_PATH           = "/var/task/global-bundle.pem"
      RUST_LOG                = "info"
      EMAIL_PROVIDER          = "ses"
      FROM_EMAIL              = var.from_email
      ADMIN_EMAIL             = var.admin_email
      S3_BUCKET               = aws_s3_bucket.uploads.id
      S3_KMS_KEY_ID           = aws_kms_key.uploads.arn
      # AI ON in staging for testing (Bedrock; no API key).
      MAJOR_FINANCE_ENABLED   = "true"
      ADMIN_ASSISTANT_ENABLED = "true"
      MAJOR_FINANCE_MODEL     = var.major_finance_model
    }
  }
  tags = { Name = "${var.project}-staging-api" }
}

resource "aws_apigatewayv2_api" "http_staging" {
  count         = local.stg
  name          = "${var.project}-staging-http-api"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins     = compact([var.staging_use_custom_domain ? "https://${var.staging_domain}" : "", "https://${aws_cloudfront_distribution.frontend_staging[0].domain_name}"])
    allow_methods     = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_headers     = ["content-type", "authorization"]
    allow_credentials = true
    max_age           = 300
  }
}

resource "aws_apigatewayv2_integration" "lambda_staging" {
  count                  = local.stg
  api_id                 = aws_apigatewayv2_api.http_staging[0].id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api_staging[0].invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "proxy_staging" {
  count     = local.stg
  api_id    = aws_apigatewayv2_api.http_staging[0].id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_staging[0].id}"
}

resource "aws_apigatewayv2_route" "root_staging" {
  count     = local.stg
  api_id    = aws_apigatewayv2_api.http_staging[0].id
  route_key = "ANY /"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_staging[0].id}"
}

resource "aws_apigatewayv2_stage" "default_staging" {
  count       = local.stg
  api_id      = aws_apigatewayv2_api.http_staging[0].id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw_staging" {
  count         = local.stg
  statement_id  = "AllowApiGwStaging"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api_staging[0].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_staging[0].execution_arn}/*/*"
}

# ── Outputs to complete the two-phase DNS setup ──────────────────────────────
output "staging_api_url" {
  description = "Staging API base URL (point the staging frontend at this)."
  value       = local.stg == 1 ? aws_apigatewayv2_api.http_staging[0].api_endpoint : ""
}

output "staging_cloudfront_domain" {
  description = "Staging CloudFront domain; add a Cloudflare CNAME staging -> this."
  value       = local.stg == 1 ? aws_cloudfront_distribution.frontend_staging[0].domain_name : ""
}

output "staging_frontend_bucket" {
  description = "S3 bucket the staging frontend deploys to."
  value       = local.stg == 1 ? aws_s3_bucket.frontend_staging[0].id : ""
}

output "staging_acm_validation" {
  description = "DNS record to add in Cloudflare to validate the staging ACM cert."
  value       = local.stg == 1 ? tolist(aws_acm_certificate.staging[0].domain_validation_options) : []
}

# ── Staging FRONTEND deploy (CodeBuild) ──────────────────────────────────────
# Rebuilds the admin SPA against the STAGING API, rewrites the prod API URL in
# the static HTML to the staging API, syncs to the staging bucket, invalidates.
#   aws codebuild start-build --project-name silenthonor-staging-frontend-deploy
resource "aws_iam_role" "staging_frontend_deploy" {
  count = local.stg
  name  = "${var.project}-staging-frontend-deploy"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "codebuild.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "staging_frontend_deploy" {
  count = local.stg
  name  = "${var.project}-staging-frontend-deploy-policy"
  role  = aws_iam_role.staging_frontend_deploy[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Sid = "Logs", Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], Resource = "*" },
      { Sid = "SyncBucket", Effect = "Allow", Action = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"], Resource = [aws_s3_bucket.frontend_staging[0].arn, "${aws_s3_bucket.frontend_staging[0].arn}/*"] },
      { Sid = "Invalidate", Effect = "Allow", Action = ["cloudfront:CreateInvalidation"], Resource = "*" }
    ]
  })
}

resource "aws_codebuild_project" "staging_frontend_deploy" {
  count        = local.stg
  name         = "${var.project}-staging-frontend-deploy"
  description  = "Build the admin SPA against staging + sync the static site to the staging bucket."
  service_role = aws_iam_role.staging_frontend_deploy[0].arn

  source {
    type            = "GITHUB"
    location        = "https://github.com/${var.github_repo}.git"
    git_clone_depth = 1
    buildspec       = <<-EOT
      version: 0.2
      phases:
        build:
          commands:
            - echo "Rebuilding admin SPA against staging API ($STAGING_API_BASE)..."
            - (cd admin-app && VITE_API_BASE="$STAGING_API_BASE" npm ci --no-audit --no-fund && npm run build)
            - echo "Rewriting prod API URL -> staging in static HTML..."
            - grep -rl "$PROD_API_BASE" --include="*.html" . | xargs -r sed -i "s#$PROD_API_BASE#$STAGING_API_BASE#g"
            - echo "Syncing to staging bucket..."
            - >
              aws s3 sync . "s3://$STAGING_BUCKET"
              --exclude ".git/*" --exclude "backend/*" --exclude "backend-rust/*" --exclude "infra/*"
              --exclude "admin-app/*" --exclude "scripts/*" --exclude "docs/*" --exclude "memory/*"
              --exclude "*.py" --exclude "*.md" --exclude "docker-compose.yml" --delete
            - aws cloudfront create-invalidation --distribution-id "$STAGING_DIST_ID" --paths "/*"
    EOT
  }
  source_version = var.github_branch

  artifacts { type = "NO_ARTIFACTS" }

  environment {
    type                        = "LINUX_CONTAINER"
    image                       = "aws/codebuild/amazonlinux2-x86_64-standard:5.0"
    compute_type                = "BUILD_GENERAL1_SMALL"
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "STAGING_BUCKET"
      value = aws_s3_bucket.frontend_staging[0].id
    }
    environment_variable {
      name  = "STAGING_DIST_ID"
      value = aws_cloudfront_distribution.frontend_staging[0].id
    }
    environment_variable {
      name  = "STAGING_API_BASE"
      value = aws_apigatewayv2_api.http_staging[0].api_endpoint
    }
    environment_variable {
      name  = "PROD_API_BASE"
      value = "https://e1tyj5meuc.execute-api.us-east-1.amazonaws.com"
    }
  }
  tags = { Name = "${var.project}-staging-frontend-deploy" }
}
