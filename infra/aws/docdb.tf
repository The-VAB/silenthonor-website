# Amazon DocumentDB — managed, MongoDB-compatible database.

resource "aws_docdb_subnet_group" "main" {
  name        = "${var.project}-docdb-subnets"
  description = "Silent Honor DocumentDB subnets" # matches live (else defaults to "Managed by Terraform")
  subnet_ids  = var.docdb_subnet_ids
  tags        = { Name = "${var.project}-docdb-subnets" }
}

resource "aws_docdb_cluster_parameter_group" "main" {
  family = "docdb5.0"
  name   = "${var.project}-docdb-params"
  # description is ForceNew; must equal live or importing replaces the param group
  # attached to the running cluster.
  description = "Silent Honor DocumentDB params"

  parameter {
    name  = "tls"
    value = "enabled"
  }
}

resource "aws_docdb_cluster" "main" {
  cluster_identifier              = "${var.project}-docdb"
  engine                          = "docdb"
  engine_version                  = "5.0.0"
  master_username                 = var.docdb_master_username
  # The real master password is managed OUT OF BAND (it is embedded in the live
  # silenthonor/mongodb-uri secret). This placeholder is never sent to AWS because
  # of ignore_changes below — it exists only to satisfy the required argument.
  master_password                 = "ManagedOutOfBand0"
  db_subnet_group_name            = aws_docdb_subnet_group.main.name
  vpc_security_group_ids          = [aws_security_group.docdb.id]
  db_cluster_parameter_group_name = aws_docdb_cluster_parameter_group.main.name

  storage_encrypted   = true
  kms_key_id          = aws_kms_key.uploads.arn
  backup_retention_period = 7
  preferred_backup_window = "03:00-04:00"
  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "${var.project}-docdb-final"

  tags = { Name = "${var.project}-docdb" }

  lifecycle {
    # master_password is write-only + managed out of band; never reconcile it.
    ignore_changes = [master_password]
  }
}

resource "aws_docdb_cluster_instance" "main" {
  count              = var.docdb_instance_count
  identifier         = "${var.project}-docdb-${count.index}"
  cluster_identifier = aws_docdb_cluster.main.id
  instance_class     = var.docdb_instance_class
  promotion_tier     = 1 # matches live (provider default is 0)
  tags               = { Name = "${var.project}-docdb-${count.index}" }
}
