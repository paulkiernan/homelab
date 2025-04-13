resource "cloudflare_zone" "bonjourinc_com" {
  account = {
    id = data.sops_file.cloudflared_creds.data["account_id"]
  }
  name = "bonjourinc.com"
}

resource "cloudflare_dns_record" "bonjour_bonjourinc_com" {
  zone_id = cloudflare_zone.bonjourinc_com.id
  name    = "bonjour.bonjourinc.com"
  type    = "CNAME"
  content = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  ttl     = 1
  proxied = true
}
resource "cloudflare_dns_record" "bonjourinc_com" {
  zone_id = cloudflare_zone.bonjourinc_com.id
  name    = "bonjourinc.com"
  type    = "CNAME"
  content = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  ttl     = 1
  proxied = true
}
resource "cloudflare_dns_record" "www_bonjourinc_com" {
  zone_id = cloudflare_zone.bonjourinc_com.id
  name    = "www.bonjourinc.com"
  type    = "CNAME"
  content = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  ttl     = 1
  proxied = true
}
