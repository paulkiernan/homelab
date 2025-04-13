/*
resource "cloudflare_zones" "paul_kiernan_com" {
  account = {
    id = data.sops_file.cloudflared_creds.data["account_id"]
  }
  name = "paul-kiernan.com"
}

resource "cloudflare_dns_record" "root_paul_kiernan_CNAME" {
  zone_id = data.cloudflare_zones.paul_kiernan_com.zones[0].id
  type    = "CNAME"
  name    = "@"
  value   = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  proxied = true
}

resource "cloudflare_dns_record" "www_paul_kiernan_CNAME" {
  zone_id = data.cloudflare_zones.paul_kiernan_com.zones[0].id
  type    = "CNAME"
  name    = "www"
  value   = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  proxied = true
}
*/
