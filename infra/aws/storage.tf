# ── KMS key for encrypting DD-214 / member documents at rest ──────────────────
resource "aws_kms_key" "uploads" {
  description             = "Silent Honor DD-214/document encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = { Name = "${var.project}-uploads-kms" }
}

resource "aws_kms_alias" "uploads" {
  name          = "alias/${var.project}-uploads"
  target_key_id = aws_kms_key.uploads.key_id
}

# ── Private uploads bucket (DD-214 + member documents) ────────────────────────
resource "aws_s3_bucket" "uploads" {
  bucket = "${var.project}-uploads-${var.account_id}"
  tags   = { Name = "${var.project}-uploads", Sensitivity = "high" }
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket                  = aws_s3_bucket.uploads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.uploads.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration { status = "Enabled" }
}

# Enforce TLS-only access to sensitive files.
resource "aws_s3_bucket_policy" "uploads_tls" {
  bucket = aws_s3_bucket.uploads.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        aws_s3_bucket.uploads.arn,
        "${aws_s3_bucket.uploads.arn}/*"
      ]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

# ── Public frontend bucket (static site, served via CloudFront OAC) ───────────
resource "aws_s3_bucket" "frontend" {
  bucket = "${var.project}-frontend-${var.account_id}"
  tags   = { Name = "${var.project}-frontend" }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  index_document { suffix = "index.html" }
  error_document { key = "404.html" }
}
