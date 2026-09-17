output "instance_name" {
  description = "Lightsail instance name."
  value       = aws_lightsail_instance.this.name
}

output "instance_arn" {
  description = "ARN of the capture instance."
  value       = aws_lightsail_instance.this.arn
}

output "static_ip" {
  description = "Attached static IPv4 address of the capture instance (phase-2 target host)."
  value       = aws_lightsail_static_ip_attachment.this.ip_address
}

output "admin_ssh" {
  description = "Admin SSH endpoint for phase 2. Authenticate with the private half of var.ssh_public_key."
  value = {
    host     = aws_lightsail_static_ip_attachment.this.ip_address
    port     = 22
    username = aws_lightsail_instance.this.username
  }
}

output "pull_connection" {
  description = "Read-only spool pull endpoint. The market-measurement-pull-ssh Secret stores only remote_host, remote_user, remote_port (plus id_ed25519 and known_hosts); remote_path here is documentation, NOT a Secret key: ssh-pull.sh fixes the client path to '/' and authorize-pull-key.sh forces `rrsync -ro /var/lib/market-recorder`, so the client path is relative to the spool root and the full spool path would double-prefix. The market-pull account is created in phase 2 by install-remote.sh --pull-public-key."
  value = {
    remote_host = aws_lightsail_static_ip_attachment.this.ip_address
    remote_user = "market-pull"
    remote_port = 22
    remote_path = "/"
  }
}

output "host_key_pinning" {
  description = "How to obtain the VM SSH host key for the phase-2 wrapper's known-hosts input (task measurement:vm-install MSR_VM_KNOWN_HOSTS, or install-remote.sh --known-hosts). Terraform cannot read host keys from the Lightsail API, so pin it through an out-of-band channel instead of trusting a bare ssh-keyscan."
  value       = "Lightsail browser console -> Connect using SSH -> cat /etc/ssh/ssh_host_ed25519_key.pub, save it as a known_hosts file, then pass it as MSR_VM_KNOWN_HOSTS (or --known-hosts); use --trust-on-first-use only as a recorded fallback."
}

output "site_id" {
  description = "Site id the phase-2 installer must seed into MARKET_RECORDER_SITE (--site); distinct from the cluster's homelab site."
  value       = local.site_id
}

output "spool_directory" {
  description = "Server-side spool path on the VM; never deleted automatically and not relocatable. The SSH-pull remote_path is '/' because rrsync is already confined to this directory."
  value       = local.spool_directory
}

output "bootstrap_directory" {
  description = "Phase-2 staging directory on the VM; install-remote.sh uploads the checksummed payload here."
  value       = "/opt/market-bootstrap"
}

output "metrics_access" {
  description = "Recorder metrics stay on loopback; reach them through an SSH tunnel as the admin user."
  value       = "tunnel: ssh -L 9090:127.0.0.1:9090 -p 22 ${aws_lightsail_instance.this.username}@${aws_lightsail_static_ip_attachment.this.ip_address} then http://127.0.0.1:9090/metrics (${local.metrics_listen} on the host, never exposed publicly)"
}

output "ssh_allowed_cidrs" {
  description = "Complete set of sources allowed to reach TCP 22 on the instance firewall."
  value       = local.ssh_allowed_cidrs
}

output "bootstrap_log" {
  description = "First-boot launch-script log on the instance."
  value       = "/var/log/cloud-init-output.log"
}

output "budget_assumption" {
  description = "Monthly-budget assumption for this stack, approved by the user."
  value       = format("Approved assumption: $%d/month for the Lightsail plan in var.bundle_id (user-quoted class: 2 vCPU / 1 GB RAM / 40 GB SSD / 2 TB transfer; confirm against aws lightsail get-bundles). Documentation only: no AWS Budget, IAM policy or service quota enforces this cap. Excludes taxes, transfer overages and snapshots. The attached static IPv4 is not billed while attached; it costs $0.005/hour if ever left unattached.", var.monthly_budget_usd)
}
