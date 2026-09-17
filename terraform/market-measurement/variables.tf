variable "aws_region" {
  description = "AWS region for the capture VM. us-east-1 is the user-approved candidate; Lightsail is available only in a subset of regions."
  type        = string
  default     = "us-east-1"
}

variable "availability_zone" {
  description = "Lightsail Availability Zone, which must be inside var.aws_region and enabled for the account. Resolve after authenticating with: aws lightsail get-regions --include-availability-zones --region <region>"
  type        = string

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9][a-z]$", var.availability_zone))
    error_message = "Use a Lightsail AZ of the form us-east-1a, as returned by aws lightsail get-regions --include-availability-zones."
  }
}

variable "blueprint_id" {
  description = "ACTIVE Lightsail blueprint id for the OS image. Use an Ubuntu LTS blueprint (ubuntu_*): the base bootstrap hardening assumes Ubuntu/Debian. Resolve after authenticating with: aws lightsail get-blueprints --region <region>"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9_]+$", var.blueprint_id))
    error_message = "blueprint_id must be a non-empty Lightsail blueprint id such as an ubuntu_* id returned by aws lightsail get-blueprints."
  }
}

variable "bundle_id" {
  description = "Lightsail bundle id for the user-approved Lightsail plan (approved class: approximately $7/month, quoted as 2 vCPU / 1 GB RAM / 40 GB SSD / 2 TB transfer). Use an x86_64 bundle: the phase-2 installer wrapper verifies the binary's ELF architecture (linux/amd64 by default). Confirm the exact id, price, specs and architecture after authenticating with: aws lightsail get-bundles --region <region>"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9_]+$", var.bundle_id))
    error_message = "bundle_id must be a non-empty Lightsail bundle id such as one returned by aws lightsail get-bundles."
  }
}

variable "instance_name" {
  description = "Lightsail instance name. Unique per region; also used to derive the key-pair and static-IP resource names, so keep it to alphanumerics, underscores and hyphens."
  type        = string
  default     = "market-measurement"

  validation {
    condition     = can(regex("^[0-9A-Za-z][0-9A-Za-z_-]{0,253}[0-9A-Za-z]$", var.instance_name))
    error_message = "instance_name must be 2-255 characters, start with an alphanumeric, and contain only alphanumerics, underscores and hyphens."
  }

  validation {
    condition     = length(var.instance_name) <= 245
    error_message = "Keep instance_name at 245 characters or fewer so the derived static IP name stays within Lightsail's name limit."
  }
}

variable "ssh_key_pair_name" {
  description = "Name of the Lightsail key pair created from var.ssh_public_key."
  type        = string
  default     = "market-measurement"

  validation {
    condition     = can(regex("^[0-9A-Za-z][0-9A-Za-z_-]{0,253}[0-9A-Za-z]$", var.ssh_key_pair_name))
    error_message = "ssh_key_pair_name must be 2-255 characters, start with an alphanumeric, and contain only alphanumerics, underscores and hyphens."
  }
}

variable "ssh_public_key" {
  description = "PUBLIC half of the admin SSH key pair, as a single bare ssh-rsa public key line. Lightsail's ImportKeyPair accepts ssh-rsa keys only (https://docs.aws.amazon.com/lightsail/2016-11-28/api-reference/API_ImportKeyPair.html); ed25519 keys cannot be imported. Private keys are never accepted, generated or stored by this configuration."
  type        = string

  validation {
    condition     = can(regex("^ssh-rsa [A-Za-z0-9+/]+={0,3}( [^\n]*)?$", trimspace(var.ssh_public_key)))
    error_message = "Provide one bare ssh-rsa public key line (ssh-rsa followed by base64 key material); Lightsail cannot import ed25519 keys."
  }
}

variable "admin_ssh_cidrs" {
  description = "IPv4 CIDRs allowed to reach TCP 22 as the admin login (operator WAN address and/or VPN CIDR). Must be non-empty: every other inbound port and source, including 9090, stays closed."
  type        = list(string)

  validation {
    condition     = length(var.admin_ssh_cidrs) > 0 && alltrue([for c in var.admin_ssh_cidrs : can(cidrnetmask(c))])
    error_message = "Provide at least one valid IPv4 CIDR for admin SSH access."
  }
}

variable "pull_ssh_cidrs" {
  description = "IPv4 CIDRs of the homelab SSH-pull client egress (the cluster's WAN egress address or its Tailscale exit address), not cluster-internal ranges. Only these plus admin_ssh_cidrs may reach TCP 22."
  type        = list(string)

  validation {
    condition     = length(var.pull_ssh_cidrs) > 0 && alltrue([for c in var.pull_ssh_cidrs : can(cidrnetmask(c))])
    error_message = "Provide at least one valid IPv4 CIDR for the read-only SSH pull client."
  }
}

variable "monthly_budget_usd" {
  description = "User-approved Lightsail plan price in whole USD per month, surfaced in the budget_assumption output. Documentation only: no AWS Budget, IAM policy or service quota enforces it. Excludes taxes, transfer overages, snapshots, and the unattached-static-IP charge."
  type        = number
  default     = 7

  validation {
    condition     = var.monthly_budget_usd > 0
    error_message = "monthly_budget_usd must be a positive number."
  }
}
