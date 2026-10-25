#!/usr/bin/env bash
set -Eeuo pipefail
RELEASE="v0.3.18"
REPO="KeygenLTD/linux-kernel-security-updater"
ARCHIVE="https://github.com/${REPO}/archive/refs/tags/${RELEASE}.tar.gz"
[[ "${EUID}" -eq 0 ]] || { echo "Run with sudo" >&2; exit 1; }
tmp="$(mktemp -d /tmp/lksu-bootstrap.XXXXXX)"; trap 'rm -rf "$tmp"' EXIT
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 "$ARCHIVE" -o "$tmp/lksu.tgz"
tar -xzf "$tmp/lksu.tgz" -C "$tmp"
root="$(find "$tmp" -maxdepth 1 -mindepth 1 -type d -name 'linux-kernel-security-updater-*' -print -quit)"
[[ -n "$root" ]] || { echo "Invalid release archive" >&2; exit 1; }
"$root/install.sh"
if [[ -s /etc/lksu/config.json ]]; then
  echo "Existing LKSU configuration preserved."
  # Prompt only on upgrade from a release with no self-update preference.
  # Explicit true/false values remain untouched on reinstall.
  if python3 - <<'PY'
import json
from pathlib import Path
try:
    cfg = json.loads(Path("/etc/lksu/config.json").read_text())
except (OSError, ValueError):
    raise SystemExit(2)
raise SystemExit(0 if "automatic_lksu_updates" not in cfg else 1)
PY
  then
    if [[ -r /dev/tty ]]; then
      /usr/local/bin/lksu configure-self-update </dev/tty >/dev/tty
    else
      echo "Self-update remains disabled; run 'lksu configure-self-update' interactively to enable it."
    fi
  fi
elif [[ -r /dev/tty ]]; then
  echo "Starting LKSU configuration."
  /usr/local/bin/lksu configure </dev/tty >/dev/tty
else
  echo "Interactive terminal is required for LKSU configuration." >&2
  exit 1
fi
if python3 - <<'PY'
import json
cfg=json.load(open('/etc/lksu/config.json'))
raise SystemExit(0 if cfg.get('automatic_reboot') and not cfg.get('recovery_ready', False) else 1)
PY
then
  echo "Automatic reboot requires a verified external snapshot, provider console access, and health checks."
  if [[ -r /dev/tty ]]; then
    if read -r -p "Configure reboot safeguards now? [y/N]: " reply </dev/tty; then
      case "${reply,,}" in
        y|yes) /usr/local/bin/lksu configure-automation </dev/tty >/dev/tty ;;
      esac
    fi
  fi
fi


echo "Enabling LKSU monitoring and verification services."
systemctl enable --now lksu.timer
systemctl enable --now lksu-security-watch.timer
systemctl enable lksu-verify.service
systemctl enable --now lksu-self-update.timer
# A read-only 15-minute assessment runs even when automatic installation is disabled.
# Existing automatic install/reboot preferences remain authoritative.
systemctl enable --now lksu-maintenance.timer


# One immediate, real kernel update attempt on first setup. The completion
# marker prevents reinstalls from repeating real kernel installations or reboots.
if [[ ! -e /var/lib/lksu/initial-run.json ]]; then
  echo "First kernel update run: installing eligible RPMs immediately when authorized."
  if ! /usr/local/bin/lksu initialize; then
    echo "Initial kernel update or controlled reboot was blocked/failed. Review the details above." >&2
    exit 1
  fi
else
  echo "Initial kernel update previously attempted successfully; running a read-only status check."
  if ! /usr/local/bin/lksu scheduled; then
    echo "Kernel status check failed; inspect logs and email delivery." >&2
    exit 1
  fi
fi
