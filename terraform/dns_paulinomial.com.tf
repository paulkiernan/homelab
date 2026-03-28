resource "cloudflare_zone" "paulinomial_com" {
  account = {
    id = "31567b61c00456dffca2206155ed1219"
  }
  name                = "paulinomial.com"
  paused              = false
  type                = "full"
  vanity_name_servers = []
}

resource "cloudflare_dns_record" "paulinomial_com_apex_CNAME" {
  content  = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  name     = "paulinomial.com"
  priority = null
  proxied  = true
  settings = {
    flatten_cname = false
    ipv4_only     = null
    ipv6_only     = null
  }
  tags    = []
  ttl     = 1
  type    = "CNAME"
  zone_id = "3a348ac001efce87cff9bebb2aeb10c1"
}

resource "cloudflare_dns_record" "paulinomial_com_www_CNAME" {
  content  = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  name     = "www.paulinomial.com"
  priority = null
  proxied  = true
  settings = {
    flatten_cname = false
    ipv4_only     = null
    ipv6_only     = null
  }
  tags    = []
  ttl     = 1
  type    = "CNAME"
  zone_id = "3a348ac001efce87cff9bebb2aeb10c1"
}
