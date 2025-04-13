/*
resource "cloudflare_zones" "paulynomial_com" {
  account = {
    id = data.sops_file.cloudflared_creds.data["account_id"]
  }
  name = "paulynomial.com"
}

resource "cloudflare_dns_record" "root_paulynomial_CNAME" {
  zone_id = data.cloudflare_zones.paulynomial_com.zones[0].id
  type    = "CNAME"
  name    = "@"
  value   = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  proxied = true
}

resource "cloudflare_dns_record" "www_paulynomial_CNAME" {
  zone_id = data.cloudflare_zones.paulynomial_com.zones[0].id
  type    = "CNAME"
  name    = "www"
  value   = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  proxied = true
}

resource "cloudflare_dns_record" "bonjour_paulynomial_CNAME" {
  zone_id = data.cloudflare_zones.paulynomial_com.zones[0].id
  type    = "CNAME"
  name    = "bonjour"
  value   = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  proxied = true
}

resource "cloudflare_dns_record" "gibson_paulynomial_CNAME" {
  zone_id = data.cloudflare_zones.paulynomial_com.zones[0].id
  type    = "CNAME"
  name    = "gibson"
  value   = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  proxied = true
}

resource "cloudflare_dns_record" "uptime_paulynomial_CNAME" {
  zone_id = data.cloudflare_zones.paulynomial_com.zones[0].id
  type    = "CNAME"
  name    = "uptime"
  value   = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  proxied = true
}

resource "cloudflare_dns_record" "upptime_paulynomial_CNAME" {
  zone_id = data.cloudflare_zones.paulynomial_com.zones[0].id
  type    = "CNAME"
  name    = "upptime"
  value   = "09925797-6349-431c-abc6-aeca6a18c50f.cfargotunnel.com"
  proxied = true
}

# Mailgun
resource "cloudflare_dns_record" "email_paulynomial_CNAME" {
  zone_id = data.cloudflare_zones.paulynomial_com.zones[0].id
  type   = "CNAME"
  name   = "email"
  value  = "mailgun.org."
}

resource "cloudflare_dns_record" "root_paulynomial_MXA" {
  zone_id = data.cloudflare_zones.paulynomial_com.zones[0].id
  type     = "MX"
  name     = "@"
  value    = "mxa.mailgun.org."
  priority = 10
}

resource "cloudflare_dns_record" "root_paulynomial_MXB" {
  zone_id = data.cloudflare_zones.paulynomial_com.zones[0].id
  type     = "MX"
  name     = "@"
  value    = "mxb.mailgun.org."
  priority = 10
}

resource "cloudflare_dns_record" "mailgun_verification_paulynomial_TXT" {
  zone_id = data.cloudflare_zones.paulynomial_com.zones[0].id
  type   = "TXT"
  name   = "@"
  value  = "v=spf1 include:mailgun.org ~all"
}

resource "cloudflare_dns_record" "k1_domainkey_paulynomial_MXB" {
  zone_id = data.cloudflare_zones.paulynomial_com.zones[0].id
  type   = "TXT"
  name   = "k1._domainkey"
  value  = "k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDSdTiengHWy2SpniS4ZLGAgkXS9pvVu+ha6oqPkQuSb1U1gHQdHGjSsFAp3i737J/eHPgUAn761cu2uzo3m6PsREK4EScK/ORjtnPTxwXPy7+Zi+KomSJ9aOdQaggvI/Sb1iINe32j1yWSJjHwWsQkKPVM8Ihp2lk6dPyJ6+srLwIDAQAB"
}

# Google Site Verification
resource "cloudflare_dns_record" "google_verification_paulynomial_TXT" {
  zone_id = data.cloudflare_zones.paulynomial_com.zones[0].id
  type   = "TXT"
  name   = "@"
  value  = "google-site-verification=kp4L1kRAl-SVwApMou_MTXIe4DXW5C3cGQXDBSaM6Gk"
}

# Keybase Site Verification
resource "cloudflare_dns_record" "keybase_verification_paulynomial_TXT" {
  zone_id = data.cloudflare_zones.paulynomial_com.zones[0].id
  type   = "TXT"
  name   = "@"
  value  = "keybase-site-verification=fpvHlqZcsUawgG7w7hWyMSqk--ywEzv8rtNr79xnU6w"
}
*/
