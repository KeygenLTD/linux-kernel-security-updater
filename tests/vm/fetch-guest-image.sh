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
# Support GNU SHA sums and Rocky's "SHA256 (filename) = digest" format.
python3 - "$name" "$CHECKSUM_ALGORITHM" <<'PY'
import hashlib, re, sys
name, algorithm = sys.argv[1:]
text = open("checksums.txt", encoding="utf-8").read()
match = None
for line in text.splitlines():
    gnu = re.fullmatch(r"([a-fA-F0-9]{64,128})\\s+\\*?(.+)", line.strip())
    bsd = re.fullmatch(r"SHA(?:256|512)\\s*\\(([^)]+)\\)\\s*=\\s*([a-fA-F0-9]{64,128})", line.strip(), re.I)
    if gnu and gnu.group(2).removeprefix("./") == name:
        match = gnu.group(1)
        break
    if bsd and bsd.group(1).removeprefix("./") == name:
        match = bsd.group(2)
        break
if match is None or len(match) != hashlib.new(algorithm).digest_size * 2:
    raise SystemExit("Image checksum absent or invalid")
digest = hashlib.new(algorithm)
with open(name, "rb") as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
if digest.hexdigest().lower() != match.lower():
    raise SystemExit("Vendor image checksum mismatch")
print("Verified vendor " + algorithm + " checksum for " + name)
PY
qemu-img info "$name"
mv "$name" guest-base.img
