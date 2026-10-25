#!/usr/bin/env bash
set -euo pipefail
umask 077
workdir="$(mktemp -d)"
qemu_pid=""
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
qemu-img create -f qcow2 -F qcow2 -b "$PWD/noble-server-cloudimg-amd64.img" "$workdir/guest.qcow2" 8G
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
       'test "$(id -u)" -ne 0 && test "$(cat /etc/os-release | grep "^ID=")" = "ID=ubuntu" && uname -r && test -d /sys/module' 2>/dev/null; then
    ready=1
    break
  fi
  sleep 5
done
if [[ "$ready" != 1 ]]; then
  echo "Isolated VM did not pass SSH/kernel smoke checks" >&2
  exit 1
fi
echo "QEMU Ubuntu guest boot and running kernel verification passed."
echo "No kernel installation, GRUB modification or reboot was attempted."
