#!/usr/bin/env python3
"""Select an installed guest kernel through GRUB for isolated VM tests."""
import pathlib
import re
import subprocess
import sys


def choose(release: str, config: str = "/boot/grub/grub.cfg") -> str:
    if not re.fullmatch(r"[A-Za-z0-9._+~-]+", release):
        raise ValueError("Invalid kernel release")
    lines = pathlib.Path(config).read_text().splitlines()
    entries = []
    depth = 0
    for line in lines:
        stripped = line.strip()
        match = re.match(r"^(menuentry|submenu) ['\"]([^'\"]+)['\"]", stripped)
        if match:
            kind, label = match.groups()
            entry_id = re.search(r"(?:--id|\\$menuentry_id_option)\\s+['\"]?([A-Za-z0-9._+~-]+)", stripped)
            entries.append((kind, entry_id.group(1) if entry_id else label, depth))
        if re.search(r"(?:^|\\s)(?:linux|linuxefi)\\s+\\S*vmlinuz-" + re.escape(release) + r"(?:\\s|$)", stripped):
            menu = ">".join(item[1] for item in entries if item[0] in ("submenu", "menuentry"))
            if not menu:
                raise ValueError("Matched kernel without GRUB menu entry")
            return menu
        depth += line.count("{") - line.count("}")
        entries = [item for item in entries if item[2] < depth]
    raise ValueError("No GRUB entry for kernel " + release)


if __name__ == "__main__":
    selection = choose(sys.argv[1])
    print("GRUB one-shot selection:", selection, flush=True)
    subprocess.run(["grub-reboot", selection], check=True)
