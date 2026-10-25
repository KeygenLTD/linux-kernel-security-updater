#!/usr/bin/env python3
"""Resolve a specific installed Linux kernel to its GRUB menu entry (CI guests only)."""
import pathlib
import re
import subprocess
import sys

def choose(release: str, config: str = "/boot/grub/grub.cfg"):
    if not re.fullmatch(r"[A-Za-z0-9._+~-]+", release):
        raise ValueError("Invalid kernel release")
    lines = pathlib.Path(config).read_text().splitlines()
    stack = []
    depth = 0
    candidate = None
    for line in lines:
        stripped = line.strip()
        is_menu = stripped.startswith(("menuentry ", "submenu "))
        if is_menu:
            kind = stripped.split(" ", 1)[0]
            ids = re.findall(r"(?:--id|\$menuentry_id_option)\s+['\"]?([A-Za-z0-9._+~-]+)", stripped)
            label = re.search(r"^(?:menuentry|submenu) ['\"]([^'\"]+)", stripped)
            parent = [part for part in stack if part[0] == "submenu"]
            current = (kind, ids[-1] if ids else (label.group(1) if label else None), depth)
            if current[1] is None:
                raise ValueError("Unrecognized GRUB menu entry")
            stack.append(current)
        if re.search(r"(?:^|\s)(?:linux|linuxefi)\s+\S*vmlinuz-" + re.escape(release) + r"(?:\s|$)", stripped):
            candidate = ">".join(part[1] for part in stack if part[0] in ("submenu", "menuentry"))
            break
        depth += line.count("{") - line.count("}")
        stack = [part for part in stack if part[2] < depth]
    if not candidate:
        raise ValueError("Installed kernel has no matching GRUB boot entry: " + release)
    return candidate

if __name__ == "__main__":
    target = choose(sys.argv[1])
    print("One-shot GRUB selection:", target)
    subprocess.run(["grub-reboot", target], check=True)
