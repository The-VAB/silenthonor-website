output "backend_url" {
  description = "App Runner HTTPS URL for the API"
  value       = "https://${aws_apprunner_service.backend.service_url}"
}

output "ecr_repository_url" {
  description = "Push the backend image here"
  value       = aws_ecr_repository.backend.repository_url
}

output "frontend_bucket" {
  description = "S3 bucket for the static frontend"
  value       = aws_s3_bucket.frontend.id
}

output "cloudfront_domain" {
  description = "CloudFront domain for the frontend"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "cloudfront_distribution_id" {
  description = "Used for cache invalidations after frontend deploys"
  value       = aws_cloudfront_distribution.frontend.id
}

output "uploads_bucket" {
  description = "Private bucket for DD-214 + member documents"
  value       = aws_s3_bucket.uploads.id
}

output "docdb_endpoint" {
  description = "DocumentDB cluster endpoint"
  value       = aws_docdb_cluster.main.endpoint
}

output "ses_dkim_tokens" {
  description = "Add these as CNAME records to verify the domain / enable DKIM in SES"
  value       = aws_sesv2_email_identity.domain.dkim_signing_attributes[0].tokens
}

output "generated_admin_password_secret" {
  description = "Secrets Manager entry holding the bootstrap admin password"
  value       = aws_secretsmanager_secret.admin_password.name
}

output "codestar_connection_arn" {
  description = "Authorize this at AWS Console -> Developer Tools -> Settings -> Connections (one-time, required before the pipeline can pull from GitHub)"
  value       = aws_codestarconnections_connection.github.arn
}

output "deploy_pipeline_name" {
  description = "CodePipeline that builds + deploys on every push to github_branch"
  value       = aws_codepipeline.deploy.name
}
