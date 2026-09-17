#!/bin/sh
# Market-measurement capture VM base bootstrap (Lightsail launch script / user_data).
#
# Phase 1 of two. This script prepares only the base host: prerequisites,
# sshd hardening, unattended security upgrades and the phase-2 staging
# directory. It deliberately fetches nothing and installs no application: the
# diff-logic-cells repository is private, so the recorder binary plus
# deploy/systemd are transferred in phase 2 by
# deploy/systemd/install-remote.sh over SCP/SSH after host-key verification and
# installed with install.sh --binary ... --start on this host.
#
# POSIX sh ONLY, on purpose. Lightsail concatenates its own instance-init
# script (which starts with `#!/bin/sh`) ahead of this user-data, so the
# combined /var/lib/cloud/instance/scripts/part-001 never keeps this shebang
# and every command here is interpreted by /bin/sh (dash on Ubuntu). A first
# version used `set -euo pipefail` and aborted with "set: Illegal option -o
# pipefail" before installing the sshd drop-in, which left cloud-init in
# status: error and the host half-hardened. Do not add bashisms (pipefail,
# arrays, [[ ]], (( )) with bare variables) to this file.
#
# Nothing here pretends the recorder is installed, and re-running it over SSH
# is safe. The launch log is /var/log/cloud-init-output.log.
set -eu

readonly BOOTSTRAP_DIR="/opt/market-bootstrap"

log() { printf 'market-base-bootstrap: %s\n' "$*"; }
die() { printf 'market-base-bootstrap: error: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "launch script must run as root"
command -v systemctl >/dev/null || die "systemd not found: use a systemd-based Ubuntu/Debian Lightsail blueprint"

# --- 1. base prerequisites --------------------------------------------------
# rsync ships rrsync, used by the phase-2 read-only pull access. openssh-server,
# tar, sha256sum and coreutils ship with the Ubuntu base image.
export DEBIAN_FRONTEND=noninteractive
missing_packages=""
for pkg in rsync openssh-server; do
  dpkg -s "$pkg" 2>/dev/null | grep -q '^Status: install ok installed' \
    || missing_packages="${missing_packages}${missing_packages:+ }${pkg}"
done
if [ -n "${missing_packages}" ]; then
  log "installing packages: ${missing_packages}"
  apt-get update -qq
  # Word splitting is intended: missing_packages is a plain space-separated list.
  # shellcheck disable=SC2086
  apt-get install -y -qq --no-install-recommends ${missing_packages}
fi

# --- 2. hardening -----------------------------------------------------------
install -d -m 0755 /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/00-market-measurement.conf <<'SSHD'
# Managed by the market-measurement Lightsail base bootstrap (user_data).
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
# Admin login accounts on Ubuntu/Debian blueprints belong to `sudo`. The
# read-only pull account joins `market-recorder` in phase 2; AllowGroups
# matches supplementary groups, which is what lets market-pull log in.
AllowGroups sudo market-recorder
SSHD
chmod 0644 /etc/ssh/sshd_config.d/00-market-measurement.conf
if systemctl is-active --quiet ssh.service; then
  systemctl reload ssh.service
fi

if dpkg -s unattended-upgrades 2>/dev/null | grep -q '^Status: install ok installed'; then
  cat > /etc/apt/apt.conf.d/20auto-upgrades <<'APT'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT
else
  log "unattended-upgrades is not installed on this blueprint; skipping automatic security updates"
fi

# --- 3. phase-2 staging directory -------------------------------------------
# install-remote.sh uploads {market-recorder,market-pull.pub,deploy/systemd/...}
# here as one checksummed tar.gz and removes the payload afterwards.
install -d -m 0755 -o root -g root "$BOOTSTRAP_DIR"

# --- 4. phase-1 verification ------------------------------------------------
for pkg in rsync openssh-server; do
  dpkg -s "$pkg" 2>/dev/null | grep -q '^Status: install ok installed' \
    || die "$pkg missing after installation"
done
# The drop-in must be in place, or the host is not hardened despite a clean exit.
[ -f /etc/ssh/sshd_config.d/00-market-measurement.conf ] \
  || die "sshd hardening drop-in missing"
for setting in 'PermitRootLogin no' 'PasswordAuthentication no' 'AllowGroups sudo market-recorder'; do
  grep -qF "$setting" /etc/ssh/sshd_config.d/00-market-measurement.conf \
    || die "hardening drop-in does not set: $setting"
done
if systemctl is-active --quiet ssh.service || systemctl is-active --quiet ssh.socket; then
  log "sshd is active with the hardened drop-in"
else
  log "sshd is not active yet; it starts from the hardened configuration on boot"
fi
log "base host ready; phase 2 will install the recorder and create /var/lib/market-recorder"
log "phase 2 (from a trusted workstation): deploy/systemd/install-remote.sh --target <admin>@<static-ip> --site <tofu output site_id> --binary <verified local linux binary> --known-hosts <pinned host key file>"
log "base bootstrap complete"
