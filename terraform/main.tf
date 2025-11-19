terraform {
  required_version = "~> 1.13.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "2.6.1"
    }
    sops = {
      source  = "carlpett/sops"
      version = "1.1.1"
    }
    cloudflare = {
      source = "cloudflare/cloudflare"
      version = "~> 5.1.0"
    }
  }

  backend "local" {
    path = "../secrets/paulynomial.tfstate"
  }
}


# Secrets management
provider sops {}

data sops_file cloudflared_creds {
  source_file = "../secrets/cloudflared.sops.yaml"
  input_type  = "yaml"
}
