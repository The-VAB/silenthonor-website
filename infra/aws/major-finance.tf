# ─────────────────────────────────────────────────────────────────────────────
# Major Finance (member AI) -- secret + IAM. Inert until enable_major_finance.
#
# This does NOT turn Major Finance on by itself. It creates the Anthropic API
# key secret and lets the Rust Lambda read it. The feature only goes live when
# the Lambda's MAJOR_FINANCE_ENABLED env var is "true" (see lambda-api.tf) AND
# every condition in docs/MAJOR_FINANCE.md is met.
#
# No secret value lives here. After apply, set the real key out of band:
#   aws secretsmanager put-secret-value \
#     --secret-id silenthonor/anthropic-api-key --secret-string 'sk-ant-...'
# ─────────────────────────────────────────────────────────────────────────────

variable "enable_major_finance" {
  description = "Provision the Anthropic key secret + IAM read for the Rust API. Off by default."
  type        = bool
  default     = false
}

variable "major_finance_model" {
  description = "Anthropic model for Major Finance. Cheaper options: claude-sonnet-5, claude-haiku-4-5."
  type        = string
  default     = "claude-opus-5"
}

locals {
  # Needs the Rust API stack too -- the IAM policy attaches to its role.
  mf_count = (var.enable_rust_api && var.enable_major_finance) ? 1 : 0
}

resource "aws_secretsmanager_secret" "anthropic" {
  count = local.mf_count
  name  = "${var.project}/anthropic-api-key"
}

# Placeholder only. Put the real key in with the CLI (above); never commit it.
resource "aws_secretsmanager_secret_version" "anthropic" {
  count         = local.mf_count
  secret_id     = aws_secretsmanager_secret.anthropic[0].id
  secret_string = "REPLACE_ME"

  lifecycle {
    # Don't let Terraform overwrite the real key on later applies.
    ignore_changes = [secret_string]
  }
}

# Let the Rust API Lambda read ONLY the Anthropic key.
resource "aws_iam_role_policy" "lambda_major_finance" {
  count = local.mf_count
  name  = "${var.project}-lambda-major-finance"
  role  = aws_iam_role.lambda_api[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "ReadAnthropicKey"
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.anthropic[0].arn]
    }]
  })
}
