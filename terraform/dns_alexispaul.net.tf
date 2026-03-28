resource "cloudflare_zone" "alexispaul_net" {
  account = {
    id = "31567b61c00456dffca2206155ed1219"
  }
  name                = "alexispaul.net"
  paused              = false
  type                = "full"
  vanity_name_servers = []
}

# Cloudflare tunnel routing
resource "cloudflare_dns_record" "alexispaul_net_apex_CNAME" {
  content  = "17d5c05c-a2c3-4f83-ad23-696251c04862.cfargotunnel.com"
  name     = "alexispaul.net"
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
  zone_id = "121c2c56cd47fa6427e018878ee20082"
}

resource "cloudflare_dns_record" "alexispaul_net_wildcard_CNAME" {
  content  = "17d5c05c-a2c3-4f83-ad23-696251c04862.cfargotunnel.com"
  name     = "*.alexispaul.net"
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
  zone_id = "121c2c56cd47fa6427e018878ee20082"
}

# Google Workspace MX records

resource "cloudflare_dns_record" "alexispaul_net_apex_MX_4" {
  content  = "aspmx.l.google.com"
  name     = "alexispaul.net"
  priority = 1
  proxied  = false
  settings = {
    flatten_cname = null
    ipv4_only     = null
    ipv6_only     = null
  }
  tags    = []
  ttl     = 3600
  type    = "MX"
  zone_id = "121c2c56cd47fa6427e018878ee20082"
}

resource "cloudflare_dns_record" "alexispaul_net_apex_MX_1" {
  content  = "alt2.aspmx.l.google.com"
  name     = "alexispaul.net"
  priority = 5
  proxied  = false
  settings = {
    flatten_cname = null
    ipv4_only     = null
    ipv6_only     = null
  }
  tags    = []
  ttl     = 3600
  type    = "MX"
  zone_id = "121c2c56cd47fa6427e018878ee20082"
}

resource "cloudflare_dns_record" "alexispaul_net_apex_MX_2" {
  content  = "alt1.aspmx.l.google.com"
  name     = "alexispaul.net"
  priority = 5
  proxied  = false
  settings = {
    flatten_cname = null
    ipv4_only     = null
    ipv6_only     = null
  }
  tags    = []
  ttl     = 3600
  type    = "MX"
  zone_id = "121c2c56cd47fa6427e018878ee20082"
}

resource "cloudflare_dns_record" "alexispaul_net_apex_MX" {
  content  = "alt4.aspmx.l.google.com"
  name     = "alexispaul.net"
  priority = 10
  proxied  = false
  settings = {
    flatten_cname = null
    ipv4_only     = null
    ipv6_only     = null
  }
  tags    = []
  ttl     = 3600
  type    = "MX"
  zone_id = "121c2c56cd47fa6427e018878ee20082"
}

resource "cloudflare_dns_record" "alexispaul_net_apex_MX_3" {
  content  = "alt3.aspmx.l.google.com"
  name     = "alexispaul.net"
  priority = 10
  proxied  = false
  settings = {
    flatten_cname = null
    ipv4_only     = null
    ipv6_only     = null
  }
  tags    = []
  ttl     = 3600
  type    = "MX"
  zone_id = "121c2c56cd47fa6427e018878ee20082"
}

# TXT records
resource "cloudflare_dns_record" "alexispaul_net_apex_TXT" {
  content  = "\"v=spf1 include:mailgun.org include:_spf.google.com ~all\""
  name     = "alexispaul.net"
  priority = null
  proxied  = false
  settings = {
    flatten_cname = null
    ipv4_only     = null
    ipv6_only     = null
  }
  tags    = []
  ttl     = 3600
  type    = "TXT"
  zone_id = "121c2c56cd47fa6427e018878ee20082"
}

resource "cloudflare_dns_record" "alexispaul_net_apex_TXT_1" {
  content  = "\"google-site-verification=NW2H6b5GSnJyIs4FFZGN1KlGzKXr-jfvnxEodMPIkzM\""
  name     = "alexispaul.net"
  priority = null
  proxied  = false
  settings = {
    flatten_cname = null
    ipv4_only     = null
    ipv6_only     = null
  }
  tags    = []
  ttl     = 3600
  type    = "TXT"
  zone_id = "121c2c56cd47fa6427e018878ee20082"
}

resource "cloudflare_dns_record" "alexispaul_net_krs_domainkey_TXT" {
  content = "k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC27AViJG6+7PBHAnPggJOR+CUH4LroXHkVU9V2uDkiMwQpad8bLk7ShdtZqm6qi3QVv5N+rfIGYOud4KxHMzszYD1dZZmiZUNz50VFWllSDYPUFb10Casp8N4k3WnpWKBvGeu9sOTQ+M+rp8A2shO73k/LfDfHWCbZaPMdpOvZsQIDAQAB"
  name    = "krs._domainkey.alexispaul.net"
  proxied = false
  ttl     = 3600
  type    = "TXT"
  zone_id = "121c2c56cd47fa6427e018878ee20082"
}

# Mailgun
resource "cloudflare_dns_record" "alexispaul_net_email_CNAME" {
  content  = "mailgun.org"
  name     = "email.alexispaul.net"
  priority = null
  proxied  = false
  settings = {
    flatten_cname = false
    ipv4_only     = null
    ipv6_only     = null
  }
  tags    = []
  ttl     = 3600
  type    = "CNAME"
  zone_id = "121c2c56cd47fa6427e018878ee20082"
}
