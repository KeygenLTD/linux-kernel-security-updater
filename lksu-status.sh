#!/usr/bin/env bash
# Read-only login indicator; never execute LKSU operations on shell login.
version="unknown"
if [[ -x /opt/lksu/current/bin/python ]]; then
  version=$(/opt/lksu/current/bin/python -c 'import importlib.metadata; print(importlib.metadata.version("lksu"))' 2>/dev/null || echo unknown)
elif [[ -x /opt/lksu/installer-env/bin/python ]]; then
  version=$(/opt/lksu/installer-env/bin/python -c 'import importlib.metadata; print(importlib.metadata.version("lksu"))' 2>/dev/null || echo unknown)
fi
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet lksu-maintenance.timer 2>/dev/null; then
  printf '\033[32mLKSU: ACTIVE | v%s\033[0m\n' "$version"
elif command -v lksu >/dev/null 2>&1; then
  printf '\033[33mLKSU: INSTALLED / INACTIVE | v%s\033[0m\n' "$version"
else
  printf '\033[31mLKSU: NOT INSTALLED\033[0m\n'
fi
