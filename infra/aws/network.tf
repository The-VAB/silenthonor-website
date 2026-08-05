# ─────────────────────────────────────────────────────────────────────────────
# Networking — REFERENCE ONLY.
#
# Silent Honor does NOT own a VPC. Its DocumentDB and App Runner ENIs live inside
# the shared "prod-vpc" (vpc-08f6c3091778e46b1, 10.1.0.0/16), which is owned and
# operated by the VAB/prod stack — NOT by this Terraform. The foundation was
# placed here by hand, so this file only *reads* the shared VPC and manages the
# two Silent-Honor-owned security groups. See STATE_RECONCILIATION.md.
#
# Consequently there is no aws_vpc / aws_subnet / aws_nat_gateway / aws_route_table
# / aws_internet_gateway / aws_vpc_endpoint here — the subnet IDs come in as
# variables (see variables.tf: shared_vpc_id, docdb_subnet_ids, apprunner_subnet_ids).
# ─────────────────────────────────────────────────────────────────────────────

data "aws_vpc" "shared" {
  id = var.shared_vpc_id
}

# ── Security groups (Silent-Honor-owned) ──────────────────────────────────────
# NOTE: `name` and `description` are immutable (ForceNew). They are set to EXACTLY
# match the live SGs so `terraform import` never triggers a replace of an SG that
# the running DocumentDB depends on.
resource "aws_security_group" "apprunner" {
  name        = "${var.project}-apprunner-sg"
  description = "Silent Honor App Runner VPC connector egress"
  vpc_id      = data.aws_vpc.shared.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.project}-apprunner-sg" }
}

resource "aws_security_group" "docdb" {
  name        = "${var.project}-docdb-sg"
  description = "Silent Honor DocumentDB - ingress from App Runner SG only"
  vpc_id      = data.aws_vpc.shared.id
  tags        = { Name = "${var.project}-docdb-sg" }

  # Ingress/egress are managed as STANDALONE rules below (not in-line) so the
  # additive Rust-API ingress rule in lambda-api.tf never fights an in-line block
  # on this SG. Mixing the two styles on one SG causes perpetual diffs.
}

resource "aws_vpc_security_group_egress_rule" "docdb_all" {
  security_group_id = aws_security_group.docdb.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "docdb_from_apprunner" {
  security_group_id            = aws_security_group.docdb.id
  referenced_security_group_id = aws_security_group.apprunner.id
  from_port                    = 27017
  to_port                      = 27017
  ip_protocol                  = "tcp"
}
