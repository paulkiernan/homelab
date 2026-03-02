terraform {
  required_version = "~> 1.14.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "2.6.1"
    }
    sops = {
      source  = "carlpett/sops"
      version = "1.3.0"
    }
    cloudflare = {
      source = "cloudflare/cloudflare"
      version = "~> 5.18.0"
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
