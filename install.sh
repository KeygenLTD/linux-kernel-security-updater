#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ${EUID} -ne 0 ]]; then echo "Run as root" >&2; exit 1; fi
source /etc/os-release
if [[ ${ID:-} != almalinux || ! ${VERSION_ID:-} =~ ^(8|9|10)(\.|$) ]]; then echo "AlmaLinux 8, 9 or 10 required" >&2; exit 1; fi
# Never install/replace the distribution Python or mutate CyberPanel environments.
# Only grubby is a kernel-management dependency.
dnf install -y grubby
PYTHON=""
for candidate in /usr/bin/python3.14 /usr/bin/python3.13 /usr/bin/python3.12 /usr/bin/python3.11 /usr/bin/python3.10 /usr/bin/python3.9 /usr/local/bin/python3.14 /usr/local/bin/python3.13 /usr/local/bin/python3.12 /usr/local/bin/python3.11 /usr/local/bin/python3.10 /usr/local/bin/python3.9; do
  [[ -x "$candidate" ]] || continue
  if "$candidate" -c 'import sys, venv, ensurepip; sys.exit(0 if (3, 9) <= sys.version_info[:2] < (3, 15) else 1)' >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done
if [[ -z "$PYTHON" ]]; then
  echo "No compatible Python 3.9-3.14 with venv/ensurepip found. Install a separate supported interpreter first; system Python and CyberPanel were not changed." >&2
  exit 1
fi
ROOT=/opt/lksu
VENV="$ROOT/installer-env"
mkdir -p "$ROOT"
if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --disable-pip-version-check --no-input "$SCRIPT_DIR"
"$VENV/bin/lksu" --help >/dev/null
# Publish stable entrypoints without changing /usr/bin/python3 or system pip.
for command in lksu lksu-fleet; do
  link="/usr/local/bin/$command"
  if [[ -e "$link" && ! -L "$link" ]]; then
    backup="$ROOT/legacy/$command"
    mkdir -p "$(dirname "$backup")"
    [[ -e "$backup" ]] || cp -p "$link" "$backup"
  fi
  ln -sfn "$VENV/bin/$command" "$link"
done
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
