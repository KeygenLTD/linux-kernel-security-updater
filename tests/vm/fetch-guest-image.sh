#!/usr/bin/env bash
set -euo pipefail
: "${IMAGE_URL:?IMAGE_URL required}"
: "${CHECKSUMS_URL:?CHECKSUMS_URL required}"
: "${CHECKSUM_ALGORITHM:?CHECKSUM_ALGORITHM required}"
case "$CHECKSUM_ALGORITHM" in sha256|sha512) ;; *) echo "Unsupported checksum algorithm" >&2; exit 2;; esac
name="${IMAGE_URL##*/}"
[[ "$name" =~ ^[A-Za-z0-9._-]+$ ]] || exit 2
curl --fail --location --retry 3 --max-time 420 --output "$name" "$IMAGE_URL"
curl --fail --location --retry 3 --max-time 120 --output checksums.txt "$CHECKSUMS_URL"
# Upstream image directory checksum files may contain additional images.
awk -v name="$name" '$2 == name || $2 == ("*" name) { print }' checksums.txt > chosen-checksum.txt
test "$(wc -l < chosen-checksum.txt)" -eq 1 || { echo "No unique upstream checksum for image" >&2; exit 2; }
"${CHECKSUM_ALGORITHM}sum" --check chosen-checksum.txt
qemu-img info "$name"
mv "$name" guest-base.img
