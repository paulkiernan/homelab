provider "cloudflare" {
  api_key = data.sops_file.cloudflared_creds.data["api_token"]
  email   = data.sops_file.cloudflared_creds.data["email"]
}
