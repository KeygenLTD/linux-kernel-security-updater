#!/usr/bin/env bash
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet lksu.timer 2>/dev/null; then
  printf '\033[32mLKSU: ACTIVE\033[0m\n'
elif command -v lksu >/dev/null 2>&1; then
  printf '\033[33mLKSU: INSTALLED / INACTIVE\033[0m\n'
else
  printf '\033[31mLKSU: NOT INSTALLED\033[0m\n'
fi
