resource "cloudflare_zone" "paul_kiernan_com" {
  account = {
    id = "31567b61c00456dffca2206155ed1219"
  }
  name                = "paul-kiernan.com"
  paused              = false
  type                = "full"
  vanity_name_servers = []
}

resource "cloudflare_dns_record" "paul_kiernan_com_apex_CNAME" {
  content  = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  name     = "paul-kiernan.com"
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
  zone_id = "b22f92a158564ff2fc9ea9c7bf55b11e"
}

resource "cloudflare_dns_record" "paul_kiernan_com_www_CNAME" {
  content  = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  name     = "www.paul-kiernan.com"
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
  zone_id = "b22f92a158564ff2fc9ea9c7bf55b11e"
}
