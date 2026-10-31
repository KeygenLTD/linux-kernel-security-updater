#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ${EUID} -ne 0 ]]; then echo "Run as root" >&2; exit 1; fi
source /etc/os-release
if [[ ${ID:-} != almalinux || ! ${VERSION_ID:-} =~ ^(8|9|10)(\.|$) ]]; then echo "AlmaLinux 8, 9 or 10 required" >&2; exit 1; fi
# Never modify system Python or CyberPanel's interpreter/environment.
# Build LKSU in its own venv with a Python supported by pyproject.toml.
dnf install -y grubby
if [[ ${VERSION_ID%%.*} == 8 ]]; then
  dnf install -y python39 python39-pip
fi
PYTHON=""
for candidate in /usr/bin/python3.13 /usr/bin/python3.12 /usr/bin/python3.11 /usr/bin/python3.10 /usr/bin/python3.9 /usr/bin/python3; do
  if [[ -x "$candidate" ]] && "$candidate" -c 'import sys,venv; assert sys.version_info >= (3,9)' 2>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done
[[ -n "$PYTHON" ]] || { echo "No supported Python >=3.9 with venv found; refusing to modify system Python." >&2; exit 1; }
VENV=/opt/lksu/venv
if [[ -e "$VENV" && ! -x "$VENV/bin/python" ]]; then
  echo "Existing LKSU venv is incomplete; refusing to overwrite it." >&2
  exit 1
fi
if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --upgrade .
install -d -m 0755 /usr/local/bin
ln -sfn "$VENV/bin/lksu" /usr/local/bin/lksu
ln -sfn "$VENV/bin/lksu-fleet" /usr/local/bin/lksu-fleet
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
