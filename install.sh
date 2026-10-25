#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ${EUID} -ne 0 ]]; then echo "Run as root" >&2; exit 1; fi
source /etc/os-release
if [[ ${ID:-} != almalinux || ! ${VERSION_ID:-} =~ ^(8|9|10)(\.|$) ]]; then echo "AlmaLinux 8, 9 or 10 required" >&2; exit 1; fi
dnf install -y python3 python3-pip python3-rpm grubby
python3 -m pip install --prefix=/usr/local .
install -D -m 0644 systemd/lksu.service /etc/systemd/system/lksu.service
install -D -m 0644 systemd/lksu.timer /etc/systemd/system/lksu.timer
install -D -m 0644 systemd/lksu-maintenance.service /etc/systemd/system/lksu-maintenance.service
install -D -m 0644 systemd/lksu-maintenance.timer /etc/systemd/system/lksu-maintenance.timer
install -D -m 0644 systemd/lksu-verify.service /etc/systemd/system/lksu-verify.service
install -D -m 0644 systemd/lksu-security-watch.service /etc/systemd/system/lksu-security-watch.service
install -D -m 0644 systemd/lksu-security-watch.timer /etc/systemd/system/lksu-security-watch.timer
install -D -m 0755 lksu-status.sh /etc/profile.d/lksu-status.sh
install -D -m 0644 systemd/lksu-self-update.service /etc/systemd/system/lksu-self-update.service
install -D -m 0644 systemd/lksu-self-update.timer /etc/systemd/system/lksu-self-update.timer
systemctl daemon-reload
systemctl enable lksu-verify.service
systemctl enable --now lksu-self-update.timer
echo "Installed. Run: lksu configure"
echo "Daily LKSU self-update timer enabled; kernel installation/reboot require the explicit configuration and recovery checks."
