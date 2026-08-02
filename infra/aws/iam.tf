# ── App Runner access role: lets the service pull the image from ECR ──────────
resource "aws_iam_role" "apprunner_access" {
  name = "${var.project}-apprunner-access"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "build.apprunner.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr" {
  role       = aws_iam_role.apprunner_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# ── App Runner instance role: the app's own AWS permissions at runtime ─────────
resource "aws_iam_role" "apprunner_instance" {
  name = "${var.project}-apprunner-instance"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "tasks.apprunner.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "apprunner_instance" {
  name = "${var.project}-apprunner-instance-policy"
  role = aws_iam_role.apprunner_instance.id
  # This MIRRORS the live-deployed role verbatim so adopting it is a 0-diff no-op.
  # The SecretsKmsDecrypt statement is redundant for the current AWS-managed-key
  # secrets (they carry no CMK); tightening the policy (dropping it, using exact
  # secret ARNs, unifying Sids) is a separate, reviewed change deliberately NOT
  # bundled into the state-reconciliation apply. See STATE_RECONCILIATION.md.
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "UploadsObjects"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.uploads.arn}/*"
      },
      {
        Sid      = "UploadsList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.uploads.arn
      },
      {
        Sid      = "UploadsKms"
        Effect   = "Allow"
        Action   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.uploads.arn
      },
      {
        Sid      = "SecretsKmsDecrypt"
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${var.region}.amazonaws.com"
          }
        }
      },
      {
        Sid      = "Ses"
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = "*"
      },
      {
        Sid      = "Secrets"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [
          aws_secretsmanager_secret.jwt.arn,
          aws_secretsmanager_secret.admin_password.arn,
          aws_secretsmanager_secret.resend.arn,
          "arn:aws:secretsmanager:${var.region}:${var.account_id}:secret:${var.project}/mongodb-uri-*",
        ]
      }
    ]
  })
}

# ── Human access: let MLugenbell trigger + monitor this pipeline only ─────────
# Scoped to exactly this pipeline/build project, matching the account's
# existing per-project deploy-policy convention (staging-consumer-deploy,
# sandbox-deploy, CI_ONLY). No S3/CloudFront/ECR/App Runner access granted --
# the pipeline's own service roles already handle every downstream step, so a
# human triggering it only ever needs to start it and read its status/logs.
data "aws_iam_user" "mlugenbell" {
  user_name = "MLugenbell"
}

resource "aws_iam_policy" "silenthonor_deploy" {
  name        = "silenthonor-deploy"
  description = "Trigger and monitor the Silent Honor deploy pipeline only"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "TriggerAndRetryPipeline"
        Effect   = "Allow"
        Action   = ["codepipeline:StartPipelineExecution", "codepipeline:RetryStageExecution"]
        Resource = [aws_codepipeline.deploy.arn]
      },
      {
        Sid    = "ReadPipelineStatus"
        Effect = "Allow"
        Action = [
          "codepipeline:GetPipeline",
          "codepipeline:GetPipelineState",
          "codepipeline:GetPipelineExecution",
          "codepipeline:ListPipelineExecutions",
        ]
        Resource = [aws_codepipeline.deploy.arn]
      },
      {
        Sid      = "ReadBuildStatus"
        Effect   = "Allow"
        Action   = ["codebuild:BatchGetBuilds", "codebuild:BatchGetProjects", "codebuild:ListBuildsForProject"]
        Resource = [aws_codebuild_project.deploy.arn]
      },
      {
        Sid      = "ReadBuildLogs"
        Effect   = "Allow"
        Action   = ["logs:GetLogEvents", "logs:FilterLogEvents", "logs:DescribeLogStreams"]
        Resource = ["arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/codebuild/${aws_codebuild_project.deploy.name}:*"]
      },
    ]
  })
}

resource "aws_iam_user_policy_attachment" "mlugenbell_silenthonor_deploy" {
  user       = data.aws_iam_user.mlugenbell.user_name
  policy_arn = aws_iam_policy.silenthonor_deploy.arn
}
