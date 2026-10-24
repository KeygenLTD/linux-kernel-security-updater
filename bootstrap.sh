#!/usr/bin/env bash
set -Eeuo pipefail
RELEASE="v0.3.7"
REPO="KeygenLTD/linux-kernel-security-updater"
ARCHIVE="https://github.com/${REPO}/archive/refs/tags/${RELEASE}.tar.gz"
[[ "${EUID}" -eq 0 ]] || { echo "Run with sudo" >&2; exit 1; }
tmp="$(mktemp -d /tmp/lksu-bootstrap.XXXXXX)"; trap 'rm -rf "$tmp"' EXIT
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 "$ARCHIVE" -o "$tmp/lksu.tgz"
tar -xzf "$tmp/lksu.tgz" -C "$tmp"
root="$(find "$tmp" -maxdepth 1 -mindepth 1 -type d -name 'linux-kernel-security-updater-*' -print -quit)"
[[ -n "$root" ]] || { echo "Invalid release archive" >&2; exit 1; }
"$root/install.sh"
if [[ -r /dev/tty ]]; then
  echo "LKSU yapılandırması başlıyor."
  /usr/local/bin/lksu configure </dev/tty >/dev/tty
else
  echo "Interactive terminal is required for LKSU configuration." >&2
  exit 1
fi
/usr/local/bin/lksu check
/usr/local/bin/lksu scheduled

echo "LKSU ilk kontrol tamamlandı; seçilen otomasyonlar etkinleştiriliyor."
systemctl enable --now lksu.timer
systemctl enable --now lksu-security-watch.timer
if python3 - <<'PY'
import json
cfg=json.load(open('/etc/lksu/config.json'))
raise SystemExit(0 if cfg.get('automatic_updates') or cfg.get('automatic_reboot') else 1)
PY
then
  systemctl enable --now lksu-maintenance.timer
fi
