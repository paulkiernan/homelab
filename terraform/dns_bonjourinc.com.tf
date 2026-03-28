resource "cloudflare_zone" "bonjourinc_com" {
  account = {
    id = "31567b61c00456dffca2206155ed1219"
  }
  name                = "bonjourinc.com"
  paused              = false
  type                = "full"
  vanity_name_servers = []
}

resource "cloudflare_dns_record" "bonjourinc_com_apex_CNAME" {
  content  = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  name     = "bonjourinc.com"
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
  zone_id = "89e9a30bbf48a2a93b89768b904e1d15"
}

resource "cloudflare_dns_record" "bonjourinc_com_www_CNAME" {
  content  = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  name     = "www.bonjourinc.com"
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
  zone_id = "89e9a30bbf48a2a93b89768b904e1d15"
}

resource "cloudflare_dns_record" "bonjourinc_com_bonjour_CNAME" {
  content  = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  name     = "bonjour.bonjourinc.com"
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
  zone_id = "89e9a30bbf48a2a93b89768b904e1d15"
}

resource "cloudflare_dns_record" "bonjourinc_com_paul_CNAME" {
  content  = "17d5c05c-a2c3-4f83-ad23-696251c04862.cfargotunnel.com"
  name     = "paul.bonjourinc.com"
  priority = null
  proxied  = false
  settings = {
    flatten_cname = false
    ipv4_only     = null
    ipv6_only     = null
  }
  tags    = []
  ttl     = 1
  type    = "CNAME"
  zone_id = "89e9a30bbf48a2a93b89768b904e1d15"
}

resource "cloudflare_dns_record" "bonjourinc_com_external_dns_cname_paul_TXT" {
  content  = "\"heritage=external-dns,external-dns/owner=external-dns-cloudflare,external-dns/resource=ingress/paulynomial-index/paulynomial\""
  name     = "_external-dns-cname-paul.bonjourinc.com"
  priority = null
  proxied  = false
  settings = {
    flatten_cname = null
    ipv4_only     = null
    ipv6_only     = null
  }
  tags    = []
  ttl     = 1
  type    = "TXT"
  zone_id = "89e9a30bbf48a2a93b89768b904e1d15"
}
