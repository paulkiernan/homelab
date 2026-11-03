resource "cloudflare_zone" "kilnbound_com" {
  account = {
    id = "31567b61c00456dffca2206155ed1219"
  }
  name = "kilnbound.com"
  type = "full"
}

# Cloudflare tunnel routing: the apex and every subdomain go through the
# cluster's cloudflared tunnel to Traefik, as for paulynomial.com.
resource "cloudflare_dns_record" "kilnbound_com_apex_CNAME" {
  content  = "17d5c05c-a2c3-4f83-ad23-696251c04862.cfargotunnel.com"
  name     = "kilnbound.com"
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
  zone_id = cloudflare_zone.kilnbound_com.id
}

resource "cloudflare_dns_record" "kilnbound_com_wildcard_CNAME" {
  content  = "17d5c05c-a2c3-4f83-ad23-696251c04862.cfargotunnel.com"
  name     = "*.kilnbound.com"
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
  zone_id = cloudflare_zone.kilnbound_com.id
}

# Email Routing: every address @kilnbound.com is forwarded to a personal inbox.
#
# cloudflare_email_routing_dns enables Email Routing on the zone and has
# Cloudflare add and lock the records it needs (three MX records, the SPF TXT
# record and the DKIM TXT record), so those are not declared here as
# cloudflare_dns_record resources. cloudflare_email_routing_settings is not
# used: it calls the deprecated enable endpoint, and in provider 5.28 its
# support_subaddress attribute fails after apply (terraform-provider-cloudflare
# issues #7386 and #7393).
resource "cloudflare_email_routing_dns" "kilnbound_com" {
  zone_id = cloudflare_zone.kilnbound_com.id
}

# The destination address is account-wide and kept in SOPS so it stays out of
# this public repository. Cloudflare emails it a verification link, and mail is
# only forwarded once that link has been followed.
resource "cloudflare_email_routing_address" "kilnbound_com_destination" {
  account_id = "31567b61c00456dffca2206155ed1219"
  email      = data.sops_file.email_routing.data["destination_email"]
}

resource "cloudflare_email_routing_catch_all" "kilnbound_com" {
  zone_id = cloudflare_zone.kilnbound_com.id
  name    = "Forward all kilnbound.com mail"
  enabled = true
  matchers = [
    {
      type = "all"
    }
  ]
  actions = [
    {
      type  = "forward"
      value = [cloudflare_email_routing_address.kilnbound_com_destination.email]
    }
  ]

  depends_on = [cloudflare_email_routing_dns.kilnbound_com]
}

# Monitoring-only DMARC policy: nothing sends mail as kilnbound.com yet.
resource "cloudflare_dns_record" "kilnbound_com_dmarc_TXT" {
  content  = "\"v=DMARC1; p=none;\""
  name     = "_dmarc.kilnbound.com"
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
  zone_id = cloudflare_zone.kilnbound_com.id
}
