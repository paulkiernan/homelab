locals {
  # Report-visible site identity, deliberately distinct from the cluster's
  # "homelab" site so a report can select this machine alone.
  site_id = "aws-${var.aws_region}"

  spool_directory = "/var/lib/market-recorder"
  metrics_listen  = "127.0.0.1:9090"

  # The only public ingress: TCP 22 from the admin and pull sources.
  ssh_allowed_cidrs = sort(distinct(concat(var.admin_ssh_cidrs, var.pull_ssh_cidrs)))

  tags = {
    Project   = "market-measurement"
    ManagedBy = "opentofu"
    Purpose   = "read-only-public-data-capture"
  }
}

# Imports the operator's PUBLIC key into Lightsail. The private half stays on
# the operator's machine and can never appear in this state.
resource "aws_lightsail_key_pair" "admin" {
  name       = var.ssh_key_pair_name
  public_key = trimspace(var.ssh_public_key)
  tags       = local.tags
}

resource "aws_lightsail_instance" "this" {
  name              = var.instance_name
  availability_zone = var.availability_zone
  blueprint_id      = var.blueprint_id
  bundle_id         = var.bundle_id
  key_pair_name     = aws_lightsail_key_pair.admin.name

  # Single-stack IPv4: the reachable surface is exactly the attached static
  # IPv4, so no IPv6 path can bypass the firewall expectations below.
  ip_address_type = "ipv4"

  # First-boot launch script (Lightsail runs it once at creation; re-running it
  # over SSH is safe). Phase 1 only: prerequisites, sshd hardening and the
  # phase-2 staging directory. The recorder binary and deploy/systemd are
  # transferred in phase 2 by deploy/systemd/install-remote.sh after host-key
  # verification, then installed with install.sh --binary ... --start.
  user_data = file("${path.module}/user-data.sh")

  tags = local.tags

  lifecycle {
    # The spool on this instance is the only copy of captured data until the
    # homelab has pulled and verified it. Refuse silent destroys/replacements
    # (user_data, key_pair_name, blueprint_id, bundle_id and availability_zone
    # are all ForceNew). Removing this guard is a deliberate decision.
    prevent_destroy = true

    # user_data is create-time bootstrap only. It runs once on first boot and
    # can never be re-applied by Terraform, so a later edit (even a pure bug
    # fix such as making the script POSIX sh) must not be read as "this
    # instance is out of date and has to be replaced" - that would destroy the
    # only copy of captured data. Post-creation configuration travels through
    # the phase-2 installer (deploy/systemd/install-remote.sh) and manual
    # remediation instead; fixing user_data only changes what FUTURE instances
    # boot with. A deliberate rebuild stays possible by removing this
    # ignore_changes together with prevent_destroy, as an explicit operator
    # decision.
    ignore_changes = [user_data]
  }
}

# Static IPv4 keeps the SSH-pull client's pinned known_hosts valid across
# stop/start and gives the firewall CIDRs a fixed destination. Attached static
# IPs are not billed separately on Lightsail.
resource "aws_lightsail_static_ip" "this" {
  name = "${var.instance_name}-static-ip"
}

resource "aws_lightsail_static_ip_attachment" "this" {
  static_ip_name = aws_lightsail_static_ip.this.name
  instance_name  = aws_lightsail_instance.this.name
}

# Assigning port_info replaces the instance firewall, so this is the complete
# inbound surface: SSH from the admin/pull CIDRs only. No 9090, no ICMP: the
# recorder metrics listener stays loopback-only.
resource "aws_lightsail_instance_public_ports" "this" {
  instance_name = aws_lightsail_instance.this.name

  port_info {
    protocol  = "tcp"
    from_port = 22
    to_port   = 22
    cidrs     = local.ssh_allowed_cidrs
  }
}
