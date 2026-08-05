# ─────────────────────────────────────────────────────────────────────────────
# CodeBuild project that compiles, tests, and packages the Rust/Lambda API.
#
# This is the build path for the Rust backend (parallel to the existing
# ${var.project}-deploy project that builds the Python image). It clones this
# repo from GitHub, runs infra/aws/buildspec-rust.yml on an ARM container, and
# drops api.zip in the pipeline artifact bucket under rust/.
#
# Inert by default (enable_rust_build = false) so it does not touch existing
# state. To use it:
#   terraform apply -var enable_rust_build=true
#   aws codebuild start-build --project-name ${var.project}-rust-build
#
# The repo is public, so CodeBuild clones it without credentials. If your account
# still requires a GitHub source authorization, use the same CodeStar connection
# the deploy pipeline uses (cicd.tf, "Update pending connection").
# ─────────────────────────────────────────────────────────────────────────────

variable "enable_rust_build" {
  description = "Create the CodeBuild project that compiles/packages the Rust Lambda."
  type        = bool
  default     = false
}

variable "rust_build_branch" {
  description = "Git branch CodeBuild pulls to build the Rust API."
  type        = string
  default     = "feat/rust-lambda-backend"
}

locals {
  rust_build_count = var.enable_rust_build ? 1 : 0
}

resource "aws_iam_role" "codebuild_rust" {
  count = local.rust_build_count
  name  = "${var.project}-codebuild-rust"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "codebuild.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "codebuild_rust" {
  count = local.rust_build_count
  name  = "${var.project}-codebuild-rust-policy"
  role  = aws_iam_role.codebuild_rust[0].id
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
        Sid      = "ArtifactPut"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject"]
        Resource = ["${aws_s3_bucket.pipeline_artifacts.arn}/rust/*"]
      }
    ]
  })
}

resource "aws_codebuild_project" "rust_build" {
  count         = local.rust_build_count
  name          = "${var.project}-rust-build"
  description   = "Compile, test, and package the Rust/Lambda API (arm64)."
  service_role  = aws_iam_role.codebuild_rust[0].arn
  build_timeout = 30

  source {
    type            = "GITHUB"
    location        = "https://github.com/${var.github_repo}.git"
    git_clone_depth = 1
    buildspec       = "infra/aws/buildspec-rust.yml"
  }
  source_version = var.rust_build_branch

  artifacts {
    type = "NO_ARTIFACTS"
  }

  environment {
    type                        = "ARM_CONTAINER"
    image                       = "aws/codebuild/amazonlinux2-aarch64-standard:3.0"
    compute_type                = "BUILD_GENERAL1_SMALL"
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "ARTIFACT_BUCKET"
      value = aws_s3_bucket.pipeline_artifacts.id
    }
  }

  tags = { Name = "${var.project}-rust-build" }
}

output "rust_build_project" {
  description = "Name of the Rust CodeBuild project (empty until enabled)."
  value       = var.enable_rust_build ? aws_codebuild_project.rust_build[0].name : ""
}
