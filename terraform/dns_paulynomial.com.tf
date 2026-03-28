resource "cloudflare_zone" "paulynomial_com" {
  account = {
    id = "31567b61c00456dffca2206155ed1219"
  }
  name                = "paulynomial.com"
  paused              = false
  type                = "full"
  vanity_name_servers = []
}

# Cloudflare tunnel routing
resource "cloudflare_dns_record" "paulynomial_com_apex_CNAME" {
  content  = "17d5c05c-a2c3-4f83-ad23-696251c04862.cfargotunnel.com"
  name     = "paulynomial.com"
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
  zone_id = "301fdc32dd813bedff26c519c3736fe6"
}

resource "cloudflare_dns_record" "paulynomial_com_CNAME" {
  content  = "17d5c05c-a2c3-4f83-ad23-696251c04862.cfargotunnel.com"
  name     = "*.paulynomial.com"
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
  zone_id = "301fdc32dd813bedff26c519c3736fe6"
}

# Mailgun
resource "cloudflare_dns_record" "paulynomial_com_apex_MX" {
  content  = "mxb.mailgun.org"
  name     = "paulynomial.com"
  priority = 10
  proxied  = false
  settings = {
    flatten_cname = null
    ipv4_only     = null
    ipv6_only     = null
  }
  tags    = []
  ttl     = 1
  type    = "MX"
  zone_id = "301fdc32dd813bedff26c519c3736fe6"
}

resource "cloudflare_dns_record" "paulynomial_com_apex_MX_1" {
  content  = "mxa.mailgun.org"
  name     = "paulynomial.com"
  priority = 10
  proxied  = false
  settings = {
    flatten_cname = null
    ipv4_only     = null
    ipv6_only     = null
  }
  tags    = []
  ttl     = 1
  type    = "MX"
  zone_id = "301fdc32dd813bedff26c519c3736fe6"
}

resource "cloudflare_dns_record" "paulynomial_com_email_CNAME" {
  content  = "mailgun.org"
  name     = "email.paulynomial.com"
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
  zone_id = "301fdc32dd813bedff26c519c3736fe6"
}

resource "cloudflare_dns_record" "paulynomial_com_k1_domainkey_TXT" {
  content  = "\"k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDSdTiengHWy2SpniS4ZLGAgkXS9pvVu+ha6oqPkQuSb1U1gHQdHGjSsFAp3i737J/eHPgUAn761cu2uzo3m6PsREK4EScK/ORjtnPTxwXPy7+Zi+KomSJ9aOdQaggvI/Sb1iINe32j1yWSJjHwWsQkKPVM8Ihp2lk6dPyJ6+srLwIDAQAB\""
  name     = "k1._domainkey.paulynomial.com"
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
  zone_id = "301fdc32dd813bedff26c519c3736fe6"
}

# TXT records
resource "cloudflare_dns_record" "paulynomial_com_apex_TXT" {
  content  = "\"keybase-site-verification=fpvHlqZcsUawgG7w7hWyMSqk--ywEzv8rtNr79xnU6w\""
  name     = "paulynomial.com"
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
  zone_id = "301fdc32dd813bedff26c519c3736fe6"
}

resource "cloudflare_dns_record" "paulynomial_com_apex_TXT_1" {
  content  = "\"v=spf1 include:mailgun.org ~all\""
  name     = "paulynomial.com"
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
  zone_id = "301fdc32dd813bedff26c519c3736fe6"
}

resource "cloudflare_dns_record" "paulynomial_com_apex_TXT_2" {
  content  = "\"google-site-verification=kp4L1kRAl-SVwApMou_MTXIe4DXW5C3cGQXDBSaM6Gk\""
  name     = "paulynomial.com"
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
  zone_id = "301fdc32dd813bedff26c519c3736fe6"
}
