#!/usr/bin/env bash
# Login banner: the recurring maintenance timer is the source of truth.
if ! command -v lksu >/dev/null 2>&1; then
  printf '\033[31mLKSU: NOT INSTALLED\033[0m\n'
elif ! command -v systemctl >/dev/null 2>&1; then
  printf '\033[33mLKSU: INSTALLED / STATUS UNKNOWN\033[0m\n'
elif systemctl is-active --quiet lksu-maintenance.timer 2>/dev/null &&
     systemctl is-enabled --quiet lksu-maintenance.timer 2>/dev/null; then
  printf '\033[32mLKSU: ACTIVE (AUTOMATIC CHECKS)\033[0m\n'
else
  printf '\033[33mLKSU: INSTALLED / INACTIVE\033[0m\n'
fi
