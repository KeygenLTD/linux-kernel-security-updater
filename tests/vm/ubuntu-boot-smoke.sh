#!/usr/bin/env bash
set -euo pipefail
umask 077
workdir="$(mktemp -d)"
qemu_pid=""
: "${EXPECTED_DISTRO:?EXPECTED_DISTRO is required}"
cleanup() {
  if [[ -n "$qemu_pid" ]]; then
    kill "$qemu_pid" 2>/dev/null || true
    wait "$qemu_pid" 2>/dev/null || true
  fi
  rm -rf "$workdir"
}
trap cleanup EXIT
ssh-keygen -q -t ed25519 -N '' -f "$workdir/id_ed25519"
pubkey="$(cat "$workdir/id_ed25519.pub")"
cat > "$workdir/user-data" <<EOF
#cloud-config
users:
  - name: lksutest
    groups: [sudo]
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - $pubkey
ssh_pwauth: false
disable_root: true
EOF
printf 'instance-id: lksu-ci-vm\nlocal-hostname: lksu-vm\n' > "$workdir/meta-data"
cloud-localds "$workdir/seed.img" "$workdir/user-data" "$workdir/meta-data"
qemu-img create -f qcow2 -F qcow2 -b "$PWD/guest-base.img" "$workdir/guest.qcow2" 8G
qemu-system-x86_64 \
  -machine accel=tcg -cpu max -smp 2 -m 2048 \
  -drive "file=$workdir/guest.qcow2,if=virtio,format=qcow2" \
  -drive "file=$workdir/seed.img,if=virtio,format=raw,readonly=on" \
  -netdev user,id=vmnet,hostfwd=tcp:127.0.0.1:22222-:22 \
  -device virtio-net-pci,netdev=vmnet \
  -display none -serial file:vm-serial.log -monitor none \
  > vm-qemu.log 2>&1 &
qemu_pid=$!
ready=0
for attempt in $(seq 1 90); do
  if ! kill -0 "$qemu_pid" 2>/dev/null; then
    echo "Guest process exited unexpectedly" >&2
    exit 1
  fi
  if ssh -i "$workdir/id_ed25519" -o StrictHostKeyChecking=no \
       -o UserKnownHostsFile=/dev/null -o ConnectTimeout=3 \
       -o BatchMode=yes -p 22222 lksutest@127.0.0.1 \
       "id -u | grep -qxv 0 && grep -qx 'ID=$EXPECTED_DISTRO' /etc/os-release && uname -r && test -d /sys/module" 2>/dev/null; then
    ready=1
    break
  fi
  sleep 5
done
if [[ "$ready" != 1 ]]; then
  echo "Isolated VM did not pass SSH/kernel smoke checks" >&2
  exit 1
fi
echo "QEMU $EXPECTED_DISTRO guest boot and running kernel verification passed."
# Compare guest boot IDs before and after a genuine system reboot.
ssh_opts=(-i "$workdir/id_ed25519" -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/dev/null -o ConnectTimeout=3 -o BatchMode=yes -p 22222)
old_kernel="$(ssh "${ssh_opts[@]}" lksutest@127.0.0.1 'uname -r')"
if [[ "${KERNEL_UPGRADE_TEST:-0}" == 1 ]]; then
  if [[ "$EXPECTED_DISTRO" != debian ]]; then
    echo "Kernel upgrade VM experiment is restricted to Debian guests." >&2
    exit 1
  fi
  echo "Installing official Debian kernel meta-package in disposable guest (no host changes)."
  ssh "${ssh_opts[@]}" lksutest@127.0.0.1 \
    'sudo timeout 900 env DEBIAN_FRONTEND=noninteractive apt-get update -qq && sudo timeout 1200 env DEBIAN_FRONTEND=noninteractive apt-get install -y linux-image-amd64' \
    > guest-package-install.log 2>&1 || { tail -60 guest-package-install.log; exit 1; }
  ssh "${ssh_opts[@]}" lksutest@127.0.0.1 'sudo dpkg-query -W -f="${Status} ${Version}\\n" linux-image-amd64; test -s "/boot/vmlinuz-$(uname -r)"' >> guest-package-install.log 2>&1 || { echo "Kernel package or old running boot image missing" >&2; exit 1; }

  echo "Selecting new installed Debian generic kernel for trial boot."
  target_kernel="$(ssh "${ssh_opts[@]}" lksutest@127.0.0.1 "find /boot -maxdepth 1 -name 'vmlinuz-*-amd64' -printf '%f\\n' | sed 's/^vmlinuz-//' | grep -v -- '-cloud-amd64' | sort -V | tail -1")"
  if [[ -z "$target_kernel" || "$target_kernel" == "$old_kernel" ]]; then
    echo "No distinct Debian generic kernel available for trial." >&2
    exit 1
  fi
  ssh "${ssh_opts[@]}" lksutest@127.0.0.1 'sudo update-grub' >> guest-package-install.log 2>&1 || { tail -80 guest-package-install.log; exit 1; }
  ssh "${ssh_opts[@]}" lksutest@127.0.0.1 "sudo python3 - '$target_kernel'" < tests/vm/guest-grub-select.py >> guest-package-install.log 2>&1 || { tail -80 guest-package-install.log; exit 1; }
  echo "Debian kernel $target_kernel staged for one-shot boot."
  ssh "${ssh_opts[@]}" lksutest@127.0.0.1 'find /boot -maxdepth 1 -name "vmlinuz-*" -type f -printf "%f\\n"' >> guest-package-install.log 2>&1

fi
old_boot_id="$(ssh "${ssh_opts[@]}" lksutest@127.0.0.1 'cat /proc/sys/kernel/random/boot_id')"
[[ "$old_boot_id" =~ ^[a-f0-9-]{36}$ ]] || { echo "Cannot read guest boot identifier" >&2; exit 1; }
ssh "${ssh_opts[@]}" lksutest@127.0.0.1 'sudo systemctl reboot' >/dev/null 2>&1 || true
rebooted=0
for attempt in $(seq 1 90); do
  if ! kill -0 "$qemu_pid" 2>/dev/null; then
    echo "QEMU guest died during reboot" >&2
    exit 1
  fi
  new_boot_id="$(ssh "${ssh_opts[@]}" lksutest@127.0.0.1 'cat /proc/sys/kernel/random/boot_id' 2>/dev/null || true)"
  if [[ "$new_boot_id" =~ ^[a-f0-9-]{36}$ ]] && [[ "$new_boot_id" != "$old_boot_id" ]]; then
    if ssh "${ssh_opts[@]}" lksutest@127.0.0.1 "grep -qx 'ID=$EXPECTED_DISTRO' /etc/os-release && test -d /sys/module && uname -r" 2>/dev/null; then
      rebooted=1
      break
    fi
  fi
  sleep 5
done
if [[ "$rebooted" != 1 ]]; then
  echo "Guest did not complete verified reboot with a changed boot ID" >&2
  exit 1
fi
echo "Verified $EXPECTED_DISTRO guest reboot: boot ID changed and guest kernel is running."
if [[ "${KERNEL_UPGRADE_TEST:-0}" == 1 ]]; then
  new_kernel="$(ssh "${ssh_opts[@]}" lksutest@127.0.0.1 'uname -r')"
  echo "Kernel before package transaction: $old_kernel"
  echo "Kernel after reboot: $new_kernel"
  if [[ "$new_kernel" == "$old_kernel" ]]; then
    echo "NO KERNEL VERSION CHANGE: official image may already have latest vendor kernel; trial is inconclusive." >&2
    exit 1
  fi

  if [[ "$new_kernel" != "$target_kernel" ]]; then
    echo "Unexpected new kernel: expected $target_kernel got $new_kernel" >&2
    exit 1
  fi
  echo "New Debian kernel verified. Selecting old kernel for one-shot rollback."
  ssh "${ssh_opts[@]}" lksutest@127.0.0.1 "sudo python3 - '$old_kernel'" < tests/vm/guest-grub-select.py >> guest-package-install.log 2>&1 || { tail -50 guest-package-install.log; exit 1; }
  rollback_before="$(ssh "${ssh_opts[@]}" lksutest@127.0.0.1 'cat /proc/sys/kernel/random/boot_id')"
  ssh "${ssh_opts[@]}" lksutest@127.0.0.1 'sudo systemctl reboot' >/dev/null 2>&1 || true
  rollback_ok=0
  for attempt in $(seq 1 90); do
    if ! kill -0 "$qemu_pid" 2>/dev/null; then echo "VM failed on rollback" >&2; exit 1; fi
    rb_id="$(ssh "${ssh_opts[@]}" lksutest@127.0.0.1 'cat /proc/sys/kernel/random/boot_id' 2>/dev/null || true)"
    if [[ "$rb_id" =~ ^[a-f0-9-]{36}$ && "$rb_id" != "$rollback_before" ]]; then
      rb_kernel="$(ssh "${ssh_opts[@]}" lksutest@127.0.0.1 'uname -r' 2>/dev/null || true)"
      if [[ "$rb_kernel" == "$old_kernel" ]]; then rollback_ok=1; break; fi
    fi
    sleep 5
  done
  if [[ "$rollback_ok" != 1 ]]; then
    echo "Rollback did not restore the original kernel $old_kernel" >&2
    exit 1
  fi
  echo "Verified actual kernel change and rollback to original Debian kernel."

else
  echo "No kernel package installation, kernel selection or rollback occurred."
fi

 | sort -V | tail -1")"
  if [[ -z "$target_kernel" || "$target_kernel" == "$old_kernel" ]]; then
    echo "No distinct Debian kernel available for trial." >&2
    exit 1
  fi
  ssh "${ssh_opts[@]}" lksutest@127.0.0.1 'sudo update-grub' >> guest-package-install.log 2>&1 || { tail -80 guest-package-install.log; exit 1; }
  ssh "${ssh_opts[@]}" lksutest@127.0.0.1 "sudo python3 - '$target_kernel'" < tests/vm/guest-grub-select.py >> guest-package-install.log 2>&1 || { tail -80 guest-package-install.log; exit 1; }
  echo "Debian kernel installed and staged for one-shot boot."
  ssh "${ssh_opts[@]}" lksutest@127.0.0.1 'find /boot -maxdepth 1 -name "vmlinuz-*" -type f -printf "%f\\n"' >> guest-package-install.log 2>&1

fi
