/*
resource "cloudflare_zones" "paulinomial_com" {
  account = {
    id = data.sops_file.cloudflared_creds.data["account_id"]
  }
  name = "paulinomial.com"
}

resource "cloudflare_dns_record" "root_paulinomial_CNAME" {
  zone_id = data.cloudflare_zones.paulinomial_com.zones[0].id
  type    = "CNAME"
  name    = "@"
  value   = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  proxied = true
}

resource "cloudflare_dns_record" "www_paulinomial_CNAME" {
  zone_id = data.cloudflare_zones.paulinomial_com.zones[0].id
  type    = "CNAME"
  name    = "www"
  value   = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  proxied = true
}
*/
