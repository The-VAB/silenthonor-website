# Generated secrets + Secrets Manager entries consumed by App Runner at runtime.

resource "random_password" "docdb" {
  length  = 24
  special = false # DocumentDB master password disallows several symbols; keep it simple
}

resource "random_password" "jwt" {
  length  = 48
  special = true
}

locals {
  # DocumentDB connection string with TLS + the CA bundle baked into the image.
  mongodb_uri = format(
    "mongodb://%s:%s@%s:27017/?tls=true&tlsCAFile=/app/rds-global-bundle.pem&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false",
    var.docdb_master_username,
    random_password.docdb.result,
    aws_docdb_cluster.main.endpoint,
  )
}

resource "aws_secretsmanager_secret" "mongodb_uri" {
  name = "${var.project}/mongodb-uri"
}
resource "aws_secretsmanager_secret_version" "mongodb_uri" {
  secret_id     = aws_secretsmanager_secret.mongodb_uri.id
  secret_string = local.mongodb_uri
}

resource "aws_secretsmanager_secret" "jwt" {
  name = "${var.project}/jwt-secret"
}
resource "aws_secretsmanager_secret_version" "jwt" {
  secret_id     = aws_secretsmanager_secret.jwt.id
  secret_string = random_password.jwt.result
}

resource "aws_secretsmanager_secret" "resend" {
  name = "${var.project}/resend-api-key"
}
resource "aws_secretsmanager_secret_version" "resend" {
  secret_id = aws_secretsmanager_secret.resend.id
  # Placeholder if not supplied; update the value in the console/CLI later.
  secret_string = var.resend_api_key != "" ? var.resend_api_key : "REPLACE_ME"
}

resource "random_password" "admin" {
  length  = 20
  special = false
}

resource "aws_secretsmanager_secret" "admin_password" {
  name = "${var.project}/admin-password"
}
resource "aws_secretsmanager_secret_version" "admin_password" {
  secret_id     = aws_secretsmanager_secret.admin_password.id
  secret_string = var.admin_password != "" ? var.admin_password : random_password.admin.result
}
