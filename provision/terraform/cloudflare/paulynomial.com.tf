// Tunnel Records
resource "cloudflare_record" "root" {
  name    = "paulynomial.com"
  proxied = true
  ttl     = 1
  type    = "CNAME"
  value   = "${data.sops_file.cloudflare_secrets.data["tunnel_id"]}.cfargotunnel.com"
  zone_id = data.sops_file.cloudflare_secrets.data["zone_id"]
}


resource "cloudflare_record" "wildcard" {
  name    = "*"
  proxied = true
  ttl     = 1
  type    = "CNAME"
  value   = "${data.sops_file.cloudflare_secrets.data["tunnel_id"]}.cfargotunnel.com"
  zone_id = data.sops_file.cloudflare_secrets.data["zone_id"]
}

// Mailgun Email Records
resource "cloudflare_record" "mailgun" {
  name    = "email"
  proxied = false
  ttl     = 1
  type    = "CNAME"
  value   = "mailgun.org"
  zone_id = data.sops_file.cloudflare_secrets.data["zone_id"]
}

resource "cloudflare_record" "mailgun_mxa_record" {
  name     = "paulynomial.com"
  priority = 10
  proxied  = false
  ttl      = 1
  type     = "MX"
  value    = "mxa.mailgun.org"
  zone_id  = data.sops_file.cloudflare_secrets.data["zone_id"]
}

resource "cloudflare_record" "mailgun_mxb_record" {
  name     = "paulynomial.com"
  priority = 10
  proxied  = false
  ttl      = 1
  type     = "MX"
  value    = "mxb.mailgun.org"
  zone_id = data.sops_file.cloudflare_secrets.data["zone_id"]
}

resource "cloudflare_record" "mailgun_txt_record" {
  name    = "paulynomial.com"
  proxied = false
  ttl     = 1
  type    = "TXT"
  value   = "v=spf1 include:mailgun.org ~all"
  zone_id = data.sops_file.cloudflare_secrets.data["zone_id"]
}

resource "cloudflare_record" "dkim" {
  name    = "k1._domainkey"
  proxied = false
  ttl     = 1
  type    = "TXT"
  value   = data.sops_file.cloudflare_secrets.data["dkim"]
  zone_id = data.sops_file.cloudflare_secrets.data["zone_id"]
}

// Google Analytics
resource "cloudflare_record" "google_analytics" {
  name    = "paulynomial.com"
  proxied = false
  ttl     = 1
  type    = "TXT"
  value   = data.sops_file.cloudflare_secrets.data["google_analytics"]
  zone_id = data.sops_file.cloudflare_secrets.data["zone_id"]
}

// Keybase
resource "cloudflare_record" "keybase_verification" {
  name    = "paulynomial.com"
  proxied = false
  ttl     = 1
  type    = "TXT"
  value   = data.sops_file.cloudflare_secrets.data["keybase"]
  zone_id = data.sops_file.cloudflare_secrets.data["zone_id"]
}
