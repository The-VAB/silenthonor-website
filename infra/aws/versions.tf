terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # Remote state lives in a dedicated, namespaced S3 bucket (created out-of-band,
  # see README). Kept separate from the VAB/Jodis state to avoid any collision.
  backend "s3" {
    bucket = "silenthonor-terraform-state-802104113048"
    key    = "silenthonor/aws/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "silenthonor"
      ManagedBy = "terraform"
      Owner     = "silent-honor-foundation"
    }
  }
}
