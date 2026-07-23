# App Runner VPC connector so the service can reach DocumentDB in private subnets.
resource "aws_apprunner_vpc_connector" "main" {
  vpc_connector_name = "${var.project}-vpc-connector"
  subnets            = aws_subnet.private[*].id
  security_groups    = [aws_security_group.apprunner.id]
}

resource "aws_apprunner_service" "backend" {
  service_name = "${var.project}-backend"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_access.arn
    }
    auto_deployments_enabled = true

    image_repository {
      image_identifier      = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port = "8000"

        runtime_environment_variables = {
          ENVIRONMENT    = "production"
          DB_NAME        = var.db_name
          AWS_REGION     = var.region
          S3_BUCKET      = aws_s3_bucket.uploads.id
          S3_KMS_KEY_ID  = aws_kms_key.uploads.arn
          EMAIL_PROVIDER = var.email_provider
          FROM_EMAIL     = var.from_email
          ADMIN_EMAIL    = var.admin_email
          CORS_ORIGINS   = join(",", var.frontend_aliases)
          FRONTEND_URL   = length(var.frontend_aliases) > 0 ? "https://${var.frontend_aliases[0]}" : "https://${aws_cloudfront_distribution.frontend.domain_name}"
        }

        runtime_environment_secrets = {
          MONGODB_URI    = aws_secretsmanager_secret.mongodb_uri.arn
          JWT_SECRET     = aws_secretsmanager_secret.jwt.arn
          RESEND_API_KEY = aws_secretsmanager_secret.resend.arn
          ADMIN_PASSWORD = aws_secretsmanager_secret.admin_password.arn
        }
      }
    }
  }

  instance_configuration {
    cpu               = var.apprunner_cpu
    memory            = var.apprunner_memory
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  network_configuration {
    egress_configuration {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.main.arn
    }
  }

  health_check_configuration {
    protocol = "HTTP"
    path     = "/health"
    interval = 20
    timeout  = 5
  }

  tags = { Name = "${var.project}-backend" }

  # The image must exist in ECR before the service can be created.
  depends_on = [aws_docdb_cluster_instance.main]
}
