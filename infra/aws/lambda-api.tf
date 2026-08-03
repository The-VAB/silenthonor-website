# ─────────────────────────────────────────────────────────────────────────────
# Rust / Lambda API (the real backend build).
#
# This runs the Rust API on Lambda behind API Gateway (HTTP API), IN THE SAME VPC
# as DocumentDB, reusing the existing secrets. It is now DEPLOYED (enable_rust_api
# defaults to true) and healthy: GET <invoke_url>/health -> {"db":"up"}. It runs
# ALONGSIDE the App Runner backend and does not disturb it — no production frontend
# points at it yet (staging cutover per docs/RUST_BACKEND.md when ready).
#
# The Lambda code ships from S3 (rust_api_s3_bucket/key); redeploy new code by
# rebuilding api.zip, uploading it, and bumping -var rust_api_source_hash. See the
# variable block below and infra/aws/buildspec-rust.yml.
#
# No secret VALUES appear here — only references to secrets that already exist.
# ─────────────────────────────────────────────────────────────────────────────

variable "enable_rust_api" {
  description = "Create/manage the Rust/Lambda API stack. TRUE now that it is deployed — leaving it false would make a default apply DESTROY the live Lambda + HTTP API."
  type        = bool
  default     = true
}

# The Lambda code is deployed from S3 (durable), not a local zip, so `terraform
# plan` never needs a build artifact on disk. Rebuild + redeploy new code by:
#   1. cargo lambda build --release --arm64  (see infra/aws/buildspec-rust.yml)
#   2. zip bootstrap + global-bundle.pem -> api.zip
#   3. aws s3 cp api.zip s3://<rust_api_s3_bucket>/<rust_api_s3_key>
#   4. set -var rust_api_source_hash=<new base64 sha256> and apply
variable "rust_api_s3_bucket" {
  description = "S3 bucket holding the packaged Lambda zip (bootstrap + CA bundle)."
  type        = string
  default     = "silenthonor-pipeline-artifacts-802104113048"
}

variable "rust_api_s3_key" {
  description = "S3 key of the packaged Lambda zip."
  type        = string
  default     = "rust/api.zip"
}

variable "rust_api_source_hash" {
  description = "base64-encoded sha256 of the Lambda zip; bump to trigger a redeploy."
  type        = string
  default     = "4sLH3Bru0bZGgAqbvwXHiZA6uZQIACyqzCnzORy/c88=" # + full admin console (analytics/apps/announcements/knowledge/LMS/staff)
}

variable "rust_api_memory_mb" {
  type    = number
  default = 512
}

variable "rust_api_timeout_s" {
  type    = number
  default = 30
}

locals {
  rust_api_count = var.enable_rust_api ? 1 : 0
}

# ── Networking: the Lambda's own SG, allowed into DocumentDB ──────────────────
resource "aws_security_group" "lambda_api" {
  count       = local.rust_api_count
  name        = "${var.project}-lambda-api-sg"
  description = "Rust API Lambda ENIs"
  vpc_id      = data.aws_vpc.shared.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.project}-lambda-api-sg" }
}

# Additive ingress on the existing DocumentDB SG: allow 27017 from the Lambda SG.
resource "aws_vpc_security_group_ingress_rule" "docdb_from_lambda" {
  count                        = local.rust_api_count
  security_group_id            = aws_security_group.docdb.id
  referenced_security_group_id = aws_security_group.lambda_api[0].id
  from_port                    = 27017
  to_port                      = 27017
  ip_protocol                  = "tcp"
  description                  = "Mongo/DocumentDB from Rust API Lambda"
}

# ── IAM: execution role + scoped secret reads ────────────────────────────────
data "aws_iam_policy_document" "lambda_assume" {
  count = local.rust_api_count
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_api" {
  count              = local.rust_api_count
  name               = "${var.project}-lambda-api-role"
  description        = "Execution role for the Silent Honor Rust/Lambda API" # matches live
  assume_role_policy = data.aws_iam_policy_document.lambda_assume[0].json
}

# Manage ENIs in the VPC + write CloudWatch logs.
resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  count      = local.rust_api_count
  role       = aws_iam_role.lambda_api[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Read ONLY the two secrets this service needs.
data "aws_iam_policy_document" "lambda_secrets" {
  count = local.rust_api_count
  statement {
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_secretsmanager_secret.jwt.arn,
      aws_secretsmanager_secret.mongodb_uri.arn,
    ]
  }
  # Transactional email (welcome + admin notification on signup), same as the
  # App Runner backend. SES resource-level scoping isn't practical for SendEmail.
  statement {
    sid       = "SendEmail"
    actions   = ["ses:SendEmail", "ses:SendRawEmail"]
    resources = ["*"]
  }
  # DD-214 upload/download: read+write the private uploads bucket under dd214/.
  statement {
    sid       = "UploadsBucket"
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${aws_s3_bucket.uploads.arn}/*"]
  }
  # SSE-KMS encrypt (put) + decrypt (presigned get) with the uploads key.
  statement {
    sid       = "UploadsKms"
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"]
    resources = [aws_kms_key.uploads.arn]
  }
}

resource "aws_iam_role_policy" "lambda_secrets" {
  count  = local.rust_api_count
  name   = "${var.project}-lambda-api-secrets"
  role   = aws_iam_role.lambda_api[0].id
  policy = data.aws_iam_policy_document.lambda_secrets[0].json
}

# ── The Lambda function ──────────────────────────────────────────────────────
resource "aws_lambda_function" "api" {
  count            = local.rust_api_count
  function_name    = "${var.project}-api"
  role             = aws_iam_role.lambda_api[0].arn
  runtime          = "provided.al2023"
  handler          = "bootstrap"
  architectures    = ["arm64"]
  s3_bucket        = var.rust_api_s3_bucket
  s3_key           = var.rust_api_s3_key
  source_code_hash = var.rust_api_source_hash
  memory_size      = var.rust_api_memory_mb
  timeout          = var.rust_api_timeout_s

  # Same private subnets as DocumentDB (they carry NAT egress for Secrets Manager).
  # Matches the live-deployed Lambda so adoption doesn't churn its ENIs.
  vpc_config {
    subnet_ids         = var.docdb_subnet_ids
    security_group_ids = [aws_security_group.lambda_api[0].id]
  }

  environment {
    variables = {
      # Secret NAMES, not values — the code resolves them via the IAM role.
      JWT_SECRET_NAME         = aws_secretsmanager_secret.jwt.name
      MONGODB_URI_SECRET_NAME = aws_secretsmanager_secret.mongodb_uri.name
      MONGODB_DB              = var.project
      # CA bundle path inside the Lambda package (see cutover step 1).
      DOCDB_CA_PATH = "/var/task/global-bundle.pem"
      RUST_LOG      = "info"

      # Transactional email (SES) -- same From as the App Runner backend.
      EMAIL_PROVIDER = "ses"
      FROM_EMAIL     = var.from_email
      ADMIN_EMAIL    = var.admin_email

      # DD-214 uploads -> private S3 bucket, SSE-KMS with the uploads key.
      S3_BUCKET     = aws_s3_bucket.uploads.id
      S3_KMS_KEY_ID = aws_kms_key.uploads.arn

      # Major Finance (member AI) -- dormant until enable_major_finance = true.
      # See major-finance.tf and docs/MAJOR_FINANCE.md.
      MAJOR_FINANCE_ENABLED         = tostring(var.enable_major_finance)
      MAJOR_FINANCE_MODEL           = var.major_finance_model
      ANTHROPIC_API_KEY_SECRET_NAME = join("", aws_secretsmanager_secret.anthropic[*].name)
    }
  }

  tags = { Name = "${var.project}-api" }
}

# ── API Gateway (HTTP API) → Lambda proxy ────────────────────────────────────
resource "aws_apigatewayv2_api" "http" {
  count         = local.rust_api_count
  name          = "${var.project}-http-api"
  protocol_type = "HTTP"

  # Same origins the live App Runner backend allows (silenthonorfoundation.org +
  # www + the CloudFront domain). The old value pointed at silenthonor.org, which
  # is not this project's domain.
  cors_configuration {
    allow_origins     = var.cors_origins
    allow_methods     = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_headers     = ["content-type", "authorization"]
    allow_credentials = true
    max_age           = 3600
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  count                  = local.rust_api_count
  api_id                 = aws_apigatewayv2_api.http[0].id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api[0].invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "proxy" {
  count     = local.rust_api_count
  api_id    = aws_apigatewayv2_api.http[0].id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda[0].id}"
}

resource "aws_apigatewayv2_route" "root" {
  count     = local.rust_api_count
  api_id    = aws_apigatewayv2_api.http[0].id
  route_key = "ANY /"
  target    = "integrations/${aws_apigatewayv2_integration.lambda[0].id}"
}

resource "aws_apigatewayv2_stage" "default" {
  count       = local.rust_api_count
  api_id      = aws_apigatewayv2_api.http[0].id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw" {
  count         = local.rust_api_count
  statement_id  = "apigw-invoke" # matches the live permission (statement_id is ForceNew)
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api[0].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http[0].execution_arn}/*/*"
}

output "rust_api_endpoint" {
  description = "Invoke URL for the Rust/Lambda API (empty until enabled)."
  value       = var.enable_rust_api ? aws_apigatewayv2_stage.default[0].invoke_url : ""
}
