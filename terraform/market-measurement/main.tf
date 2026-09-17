terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source = "hashicorp/aws"
      # Deliberately pinned. Lightsail resources used here are stable across
      # the 6.x line; verify https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lightsail_instance
      # before bumping. Installed by Main with `tofu init` once AWS credentials exist.
      version = "6.64.0"
    }
  }

  backend "local" {
    path = "terraform.tfstate"
  }

  # State stays local and is git-ignored by default (see .gitignore). Commit it
  # only if TF_ENCRYPTION enforcement is a deliberate decision for this root;
  # state here contains CIDRs, public keys and URLs, never private key material.
}

provider "aws" {
  region = var.aws_region
}
