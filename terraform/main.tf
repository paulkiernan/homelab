terraform {
  required_version = ">= 1.7.0"

  required_providers {
    sops = {
      source  = "carlpett/sops"
      version = "1.4.1"
    }
    cloudflare = {
      source = "cloudflare/cloudflare"
      version = "~> 5.19.0"
    }
  }

  backend "local" {
    path = "terraform.tfstate"
  }

  # State encryption config is injected at runtime via TF_ENCRYPTION env var.
  # The Taskfile tasks (terraform:plan, terraform:apply, etc.) handle this
  # automatically by decrypting the passphrase from state-encryption.sops.yaml.
  # See: https://opentofu.org/docs/language/state/encryption/
}


# Secrets management
provider sops {}

data sops_file cloudflared_creds {
  source_file = "../secrets/cloudflared.sops.yaml"
  input_type  = "yaml"
}
