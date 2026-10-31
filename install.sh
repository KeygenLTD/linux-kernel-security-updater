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
# Stage and verify before touching the active command. Never replace a working
# installation with an untested environment.
VENV=/opt/lksu/venv
STAGE=$(mktemp -d /opt/lksu/.venv-stage.XXXXXXXX)
cleanup() { if [[ -d "$STAGE" ]]; then rm -rf -- "$STAGE"; fi; }
trap cleanup EXIT
"$PYTHON" -m venv "$STAGE"
"$STAGE/bin/python" -m pip --version >/dev/null || {
  echo "venv pip unavailable; existing LKSU remains unchanged" >&2
  exit 1
}
"$STAGE/bin/python" -m pip install .
"$STAGE/bin/python" -c 'from lksu.cli import main; from lksu.fleet import main as fleet_main'
"$STAGE/bin/lksu" --help >/dev/null
if [[ -e "$VENV" || -L "$VENV" ]]; then
  echo "Existing $VENV detected; refusing to overwrite it automatically." >&2
  exit 1
fi
mv -- "$STAGE" "$VENV"
trap - EXIT
# A venv moved after creation can contain absolute paths to its staging
# directory. Regenerate console entrypoints with the final venv location.
"$VENV/bin/python" -m pip install --force-reinstall --no-deps --no-build-isolation .
"$VENV/bin/lksu" --help >/dev/null
install -d -m 0755 /usr/local/bin
for cmd in lksu lksu-fleet; do
  link="/usr/local/bin/$cmd"
  tmp="/usr/local/bin/.$cmd.new.$"
  ln -s "$VENV/bin/$cmd" "$tmp"
  mv -Tf "$tmp" "$link"
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
