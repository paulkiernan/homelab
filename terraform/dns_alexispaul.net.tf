resource "cloudflare_zone" "alexispaul_net" {
  account = {
    id = data.sops_file.cloudflared_creds.data["account_id"]
  }
  name = "alexispaul.net"
}

resource "cloudflare_dns_record" "root_paulynomial_MXA" {
  zone_id  = cloudflare_zone.alexispaul_net.id
  type     = "MX"
  name     = "alexispaul.net"
  content  = "mxa.mailgun.org."
  priority = 10
  ttl      = 3600
}

resource "cloudflare_dns_record" "root_paulynomial_MXB" {
  zone_id  = cloudflare_zone.alexispaul_net.id
  type     = "MX"
  name     = "alexispaul.net"
  content  = "mxb.mailgun.org."
  priority = 10
  ttl      = 3600
}

resource "cloudflare_dns_record" "mailgun_verification_paulynomial_TXT" {
  zone_id = cloudflare_zone.alexispaul_net.id
  type    = "TXT"
  name    = "@"
  content = "v=spf1 include:mailgun.org ~all"
  ttl      = 3600
}

resource "cloudflare_dns_record" "k1_domainkey_paulynomial_MXB" {
  zone_id = cloudflare_zone.alexispaul_net.id
  type    = "TXT"
  name    = "krs._domainkey.alexispaul.net"
  content = "k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC27AViJG6+7PBHAnPggJOR+CUH4LroXHkVU9V2uDkiMwQpad8bLk7ShdtZqm6qi3QVv5N+rfIGYOud4KxHMzszYD1dZZmiZUNz50VFWllSDYPUFb10Casp8N4k3WnpWKBvGeu9sOTQ+M+rp8A2shO73k/LfDfHWCbZaPMdpOvZsQIDAQAB"
  ttl      = 3600
}

resource "cloudflare_dns_record" "email_alexispaul_CNAME" {
  zone_id = cloudflare_zone.alexispaul_net.id
  type    = "CNAME"
  name    = "email.alexispaul.net"
  content = "mailgun.org."
  ttl      = 3600
}
