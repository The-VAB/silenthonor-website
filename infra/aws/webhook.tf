# ── Webhook receiver: GitHub push -> Lambda -> StartPipelineExecution ─────────
#
# Fallback trigger mechanism. The pipeline's CodeStarSourceConnection reads the
# repo fine (Source stage succeeds on every run), but its automatic
# DetectChanges trigger relies on the AWS-managed "AWS Connector for GitHub"
# App having repository access -- not installable on this GitHub org's policy.
# This plain repo webhook supplies the same "a push happened" signal instead.
#
# One-time setup after `terraform apply` (on GitHub, not AWS):
#   terraform output webhook_url
#   aws secretsmanager get-secret-value --secret-id "$(terraform output -raw webhook_secret_arn)" \
#     --query SecretString --output text
#   Then: GitHub repo -> Settings -> Webhooks -> Add webhook
#     Payload URL:  <webhook_url>
#     Content type: application/json
#     Secret:       <value from the secretsmanager command above>
#     Events:       just the push event

resource "random_password" "github_webhook" {
  length  = 40
  special = false
}

resource "aws_secretsmanager_secret" "github_webhook" {
  name = "${var.project}/github-webhook-secret"
}

resource "aws_secretsmanager_secret_version" "github_webhook" {
  secret_id     = aws_secretsmanager_secret.github_webhook.id
  secret_string = random_password.github_webhook.result
}

data "archive_file" "webhook_trigger" {
  type        = "zip"
  source_file = "${path.module}/lambda/webhook_trigger.py"
  output_path = "${path.module}/lambda/webhook_trigger.zip"
}

resource "aws_iam_role" "webhook_trigger" {
  name = "${var.project}-webhook-trigger"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "webhook_trigger" {
  name = "${var.project}-webhook-trigger-policy"
  role = aws_iam_role.webhook_trigger.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "Logs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      },
      {
        Sid      = "ReadWebhookSecret"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.github_webhook.arn]
      },
      {
        Sid      = "StartPipeline"
        Effect   = "Allow"
        Action   = ["codepipeline:StartPipelineExecution"]
        Resource = [aws_codepipeline.deploy.arn]
      }
    ]
  })
}

resource "aws_lambda_function" "webhook_trigger" {
  function_name    = "${var.project}-webhook-trigger"
  role             = aws_iam_role.webhook_trigger.arn
  handler          = "webhook_trigger.handler"
  runtime          = "python3.12"
  timeout          = 10
  filename         = data.archive_file.webhook_trigger.output_path
  source_code_hash = data.archive_file.webhook_trigger.output_base64sha256

  environment {
    variables = {
      PIPELINE_NAME      = aws_codepipeline.deploy.name
      BRANCH             = var.github_branch
      WEBHOOK_SECRET_ARN = aws_secretsmanager_secret.github_webhook.arn
    }
  }

  tags = { Name = "${var.project}-webhook-trigger" }
}

# NONE auth is correct here: GitHub webhooks can't sign with SigV4, so the
# function itself verifies the X-Hub-Signature-256 HMAC against the shared
# secret above before doing anything.
resource "aws_lambda_function_url" "webhook_trigger" {
  function_name      = aws_lambda_function.webhook_trigger.function_name
  authorization_type = "NONE"
}
