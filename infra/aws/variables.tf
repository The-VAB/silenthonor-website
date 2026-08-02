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

# ── Networking (reference-only; see network.tf + STATE_RECONCILIATION.md) ──────
# Silent Honor lives inside the shared prod-vpc; it does not create networking.
variable "shared_vpc_id" {
  description = "ID of the shared prod-vpc hosting Silent Honor's DocumentDB + App Runner ENIs"
  type        = string
  default     = "vpc-08f6c3091778e46b1"
}

variable "docdb_subnet_ids" {
  description = "Shared prod-private subnets backing the DocumentDB subnet group"
  type        = list(string)
  default = [
    "subnet-060bcae134dabaccf",
    "subnet-0fb8e82e523f72559",
    "subnet-02ccdbaa719f0c9f4",
  ]
}

variable "apprunner_subnet_ids" {
  description = "Dedicated silenthonor-apprunner subnets for App Runner + Rust Lambda ENIs"
  type        = list(string)
  default = [
    "subnet-06e8bddabd7060b7f",
    "subnet-09bce5130d93f55fc",
  ]
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
  default     = "ses" # production was cut over to SES (verified + DKIM SUCCESS); matches live App Runner env
}

variable "from_email" {
  description = "From address for outbound email"
  type        = string
  default     = "Silent Honor <no-reply@silenthonorfoundation.org>" # matches live (note the hyphen in no-reply)
}

# Allowed CORS origins for the backend API — full scheme+host, as the live App
# Runner service is configured. NOTE: this differs from frontend_aliases (bare
# hosts) on purpose; browser Origin headers include the scheme, and the live set
# also allows the CloudFront default domain.
variable "cors_origins" {
  description = "CORS allow-list for the backend API (matches live App Runner CORS_ORIGINS)"
  type        = list(string)
  default = [
    "https://silenthonorfoundation.org",
    "https://www.silenthonorfoundation.org",
    "https://d27zjlncmljktr.cloudfront.net",
  ]
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
# Defaults match the live DNS cutover done via scripts/aws-finalize-domains.sh
# (see infra/aws/README.md) -- empty aliases would detach the real custom
# domains from the live CloudFront distribution.
variable "frontend_aliases" {
  description = "Custom domain aliases for the CloudFront frontend. Empty = use the default *.cloudfront.net domain (no ACM cert needed)."
  type        = list(string)
  default     = ["silenthonorfoundation.org", "www.silenthonorfoundation.org"]
}

variable "acm_certificate_arn" {
  description = "ACM cert ARN (us-east-1) for frontend_aliases. Required only if aliases are set."
  type        = string
  default     = "arn:aws:acm:us-east-1:802104113048:certificate/a10f91e0-fa27-4b5b-b284-07a7e8ec0351"
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

# ── CI/CD ─────────────────────────────────────────────────────────────────────
variable "github_repo" {
  description = "GitHub repo the deploy pipeline watches, as owner/repo"
  type        = string
  default     = "The-VAB/silenthonor-website"
}

variable "github_branch" {
  description = "Branch that triggers a deploy on push"
  type        = string
  default     = "main"
}
