# ─────────────────────────────────────────────────────────────────────────────
# Secrets Manager entries consumed by App Runner (and the Rust API) at runtime.
#
# Terraform owns the secret CONTAINERS but NOT their VALUES. The live secrets
# already hold real production credentials (JWT signing key, the DocumentDB
# connection URI with its master password, the Resend API key, the bootstrap
# admin password). `ignore_changes = [secret_string]` guarantees a plan/apply
# never rewrites a live credential, and there are deliberately no random_password
# resources here anymore — generating fresh values would have reset the running
# database password and invalidated every issued JWT. See STATE_RECONCILIATION.md.
#
# To rotate a value, do it out of band:
#   aws secretsmanager put-secret-value --secret-id silenthonor/<name> --secret-string '...'
# ─────────────────────────────────────────────────────────────────────────────

locals {
  # Placeholder written only if a secret is ever created from scratch; on the
  # existing (imported) secrets it is ignored via ignore_changes below.
  managed_out_of_band = "managed-out-of-band"
}

resource "aws_secretsmanager_secret" "mongodb_uri" {
  name = "${var.project}/mongodb-uri"
}
resource "aws_secretsmanager_secret_version" "mongodb_uri" {
  secret_id     = aws_secretsmanager_secret.mongodb_uri.id
  secret_string = local.managed_out_of_band
  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "jwt" {
  name = "${var.project}/jwt-secret"
}
resource "aws_secretsmanager_secret_version" "jwt" {
  secret_id     = aws_secretsmanager_secret.jwt.id
  secret_string = local.managed_out_of_band
  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "resend" {
  name = "${var.project}/resend-api-key"
}
resource "aws_secretsmanager_secret_version" "resend" {
  secret_id     = aws_secretsmanager_secret.resend.id
  secret_string = local.managed_out_of_band
  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "admin_password" {
  name = "${var.project}/admin-password"
}
resource "aws_secretsmanager_secret_version" "admin_password" {
  secret_id     = aws_secretsmanager_secret.admin_password.id
  secret_string = local.managed_out_of_band
  lifecycle {
    ignore_changes = [secret_string]
  }
}
