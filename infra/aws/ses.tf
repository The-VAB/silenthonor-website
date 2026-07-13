# SES domain identity for sending as @silenthonorfoundation.org.
# Verification + DKIM require DNS records at the domain registrar; the exact
# records are exposed as outputs (dkim_tokens). Until DNS is added and the
# account is out of the SES sandbox, keep EMAIL_PROVIDER=resend.
resource "aws_sesv2_email_identity" "domain" {
  email_identity = var.email_domain
}
