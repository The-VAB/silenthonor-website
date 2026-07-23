variable "region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Resource name prefix"
  type        = string
  default     = "silenthonor"
}

variable "account_id" {
  description = "AWS account ID (used to make S3 bucket names globally unique)"
  type        = string
  default     = "802104113048"
}

# ── Networking ────────────────────────────────────────────────────────────────
variable "vpc_cidr" {
  description = "CIDR for the Silent Honor VPC (kept clear of existing 10.0/10.1 VPCs)"
  type        = string
  default     = "10.20.0.0/16"
}

variable "az_count" {
  description = "Number of AZs (DocumentDB subnet group needs >= 2)"
  type        = number
  default     = 2
}

# ── DocumentDB ────────────────────────────────────────────────────────────────
variable "docdb_instance_class" {
  description = "DocumentDB instance class. db.t3.medium is the smallest / cheapest."
  type        = string
  default     = "db.t3.medium"
}

variable "docdb_instance_count" {
  description = "Number of DocumentDB instances (1 = single-instance, cheapest)"
  type        = number
  default     = 1
}

variable "docdb_master_username" {
  description = "DocumentDB master username"
  type        = string
  default     = "shadmin"
}

variable "db_name" {
  description = "Application database name"
  type        = string
  default     = "silenthonor"
}

# ── Backend (App Runner) ──────────────────────────────────────────────────────
variable "backend_image_tag" {
  description = "Image tag in ECR that App Runner deploys"
  type        = string
  default     = "latest"
}

variable "apprunner_cpu" {
  description = "App Runner vCPU (in units, e.g. 1024 = 1 vCPU)"
  type        = string
  default     = "1024"
}

variable "apprunner_memory" {
  description = "App Runner memory (MB)"
  type        = string
  default     = "2048"
}

# ── Email ─────────────────────────────────────────────────────────────────────
variable "email_provider" {
  description = "resend or ses"
  type        = string
  default     = "resend"
}

variable "from_email" {
  description = "From address for outbound email"
  type        = string
  default     = "Silent Honor <noreply@silenthonorfoundation.org>"
}

variable "email_domain" {
  description = "Domain to verify in SES for sending"
  type        = string
  default     = "silenthonorfoundation.org"
}

variable "resend_api_key" {
  description = "Resend API key (leave blank to set later in Secrets Manager)"
  type        = string
  default     = ""
  sensitive   = true
}

# ── Frontend ──────────────────────────────────────────────────────────────────
variable "frontend_aliases" {
  description = "Custom domain aliases for the CloudFront frontend. Empty = use the default *.cloudfront.net domain (no ACM cert needed)."
  type        = list(string)
  default     = []
}

variable "acm_certificate_arn" {
  description = "ACM cert ARN (us-east-1) for frontend_aliases. Required only if aliases are set."
  type        = string
  default     = ""
}

# ── App secrets (seeded into Secrets Manager) ─────────────────────────────────
variable "admin_email" {
  description = "Bootstrap admin email"
  type        = string
  default     = "admin@silenthonorfoundation.org"
}

variable "admin_password" {
  description = "Bootstrap admin password (change after first login)"
  type        = string
  default     = ""
  sensitive   = true
}
