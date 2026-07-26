# ─────────────────────────────────────────────────────────────────────────────
# Rust / Lambda API (the real backend build).
#
# This stands up the Rust API on Lambda behind API Gateway (HTTP API), IN THE SAME
# VPC as DocumentDB, reusing the existing secrets. It is INERT by default
# (enable_rust_api = false) so it never disturbs the current App Runner deploy.
#
# Tyler's cutover steps (see docs/RUST_BACKEND.md):
#   1. Build the arm64 artifact:  cd backend-rust && cargo lambda build --release --arm64
#      then zip target/lambda/bootstrap/bootstrap  ->  set rust_api_zip_path.
#      (Bundle the DocumentDB CA `global-bundle.pem` into the zip root too.)
#   2. terraform apply -var enable_rust_api=true -var rust_api_zip_path=...
#   3. Point a staging frontend's window.API_BASE at the api_gateway output, verify,
#      then flip production.
#
# No secret VALUES appear here — only references to secrets that already exist.
# ─────────────────────────────────────────────────────────────────────────────

variable "enable_rust_api" {
  description = "Create the Rust/Lambda API stack. Off until the build artifact exists."
  type        = bool
  default     = false
}

variable "rust_api_zip_path" {
  description = "Path to the packaged Lambda zip (bootstrap + CA bundle)."
  type        = string
  default     = ""
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
  vpc_id      = aws_vpc.main.id

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
  filename         = var.rust_api_zip_path
  source_code_hash = filebase64sha256(var.rust_api_zip_path)
  memory_size      = var.rust_api_memory_mb
  timeout          = var.rust_api_timeout_s

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
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
    }
  }

  tags = { Name = "${var.project}-api" }
}

# ── API Gateway (HTTP API) → Lambda proxy ────────────────────────────────────
resource "aws_apigatewayv2_api" "http" {
  count         = local.rust_api_count
  name          = "${var.project}-http-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins     = ["https://silenthonor.org", "https://www.silenthonor.org"]
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
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api[0].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http[0].execution_arn}/*/*"
}

output "rust_api_endpoint" {
  description = "Invoke URL for the Rust/Lambda API (empty until enabled)."
  value       = var.enable_rust_api ? aws_apigatewayv2_stage.default[0].invoke_url : ""
}
