"""Debian-family kernel package discovery and GRUB entry planning.

This module performs no host mutations on import. Installation and reboot
are deliberately separate operations so callers can persist rollback state.
"""
import pathlib
import re
import subprocess

RELEASE = re.compile(r"^[A-Za-z0-9._+~-]+$")


from .core import LKSUError


class DebianKernelError(LKSUError):
    pass


def kernel_package(distro_id, flavor="generic"):
    if distro_id == "debian":
        return "linux-image-amd64"
    if distro_id == "ubuntu":
        if flavor not in {"generic", "virtual"}:
            raise DebianKernelError("Unsupported Ubuntu kernel flavor")
        return "linux-image-" + flavor
    raise DebianKernelError("Not a supported Debian-family distribution")


def boot_images(boot=pathlib.Path("/boot")):
    images = {}
    for image in boot.glob("vmlinuz-*"):
        release = image.name[len("vmlinuz-"):]
        if RELEASE.fullmatch(release) and image.is_file():
            images[release] = image
    return images


def select_candidate(before, after, installed_release):
    """A distinct installed image must exist; never infer from apt exit status."""
    if not RELEASE.fullmatch(installed_release):
        raise DebianKernelError("Invalid running kernel release")
    if installed_release not in before:
        raise DebianKernelError("Running kernel image missing before update")
    if installed_release not in after:
        raise DebianKernelError("Original kernel image disappeared during update")
    candidates = sorted(set(after) - set(before))
    if len(candidates) != 1:
        raise DebianKernelError("Expected exactly one newly installed kernel; manual selection required")
    return candidates[0]


def install_kernel(distro_id, running_release, *, flavor="generic", runner=subprocess.run):
    """Install a vendor kernel without autoremove; retain original boot image.

    Caller must snapshot/persist original boot state and perform guarded trial
    selection before any reboot. Does not reboot or alter GRUB defaults.
    """
    if not RELEASE.fullmatch(running_release):
        raise DebianKernelError("Invalid running kernel release")
    package = kernel_package(distro_id, flavor)
    before = boot_images()
    if running_release not in before:
        raise DebianKernelError("Running kernel boot image is absent")
    for args in (["apt-get", "update", "-qq"],
                 ["apt-get", "install", "-y", "--no-install-recommends", package]):
        try:
            result = runner(args, check=False, timeout=1800)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DebianKernelError("APT transaction failed: " + str(exc)) from exc
        if result.returncode != 0:
            raise DebianKernelError("APT transaction failed; inspect package manager logs")
    after = boot_images()
    return {"previous": running_release,
            "candidate": select_candidate(before, after, running_release),
            "package": package, "rebooted": False}


def check_host(distro_id, running_release):
    """Read-only Debian/Ubuntu kernel readiness check; no apt or boot mutation."""
    package = kernel_package(distro_id)
    images = boot_images()
    if not RELEASE.fullmatch(running_release) or running_release not in images:
        raise DebianKernelError("Running kernel image is missing or invalid")
    result = subprocess.run(["dpkg-query", "-W", "-f=${Status}", package],
                            capture_output=True, text=True, check=False, timeout=30)
    if result.returncode not in (0, 1):
        raise DebianKernelError("Cannot query vendor kernel metapackage")
    return {"distribution": distro_id, "running": running_release,
            "kernel_metapackage": package,
            "metapackage_installed": result.returncode == 0 and
            result.stdout.strip() == "install ok installed",
            "installed_boot_images": sorted(images),
            "status": "inventory-only"}


def grub_menu_entry(release, config=pathlib.Path("/boot/grub/grub.cfg")):
    """Resolve a GRUB one-shot menu path from the actual guest configuration."""
    if not RELEASE.fullmatch(release):
        raise DebianKernelError("Invalid kernel release")
    if not config.is_file():
        raise DebianKernelError("GRUB configuration missing")
    lines = config.read_text().splitlines()
    stack = []
    depth = 0
    for line in lines:
        stripped = line.strip()
        match = re.match(r"^(menuentry|submenu) ['\"]([^'\"]+)['\"]", stripped)
        if match:
            kind, label = match.groups()
            identifier = re.search(r"(?:--id|\$menuentry_id_option)\s+['\"]?([A-Za-z0-9._+~-]+)", stripped)
            stack.append((kind, identifier.group(1) if identifier else label, depth))
        if re.search(r"(?:^|\s)(?:linux|linuxefi)\s+\S*vmlinuz-" + re.escape(release) + r"(?:\s|$)", stripped):
            path = ">".join(item[1] for item in stack)
            if not path:
                raise DebianKernelError("Kernel found outside GRUB menu")
            return path
        depth += line.count("{") - line.count("}")
        stack = [entry for entry in stack if entry[2] < depth]
    raise DebianKernelError("Kernel missing from GRUB menu")


def stage_one_shot(release, *, runner=subprocess.run, config=pathlib.Path("/boot/grub/grub.cfg")):
    """Stage a trial boot; do not reboot or change the persistent default."""
    if release not in boot_images():
        raise DebianKernelError("Candidate boot image missing")
    entry = grub_menu_entry(release, config)
    try:
        result = runner(["grub-reboot", entry], check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DebianKernelError("GRUB one-shot selection failed") from exc
    if result.returncode:
        raise DebianKernelError("GRUB one-shot selection failed")
    return {"candidate": release, "trial_entry": entry, "rebooted": False}


def apply_managed(distro_id, running_release, state_path, *, flavor="generic"):
    """Install and persist a trial candidate before changing next-boot state.

    Refuse to overwrite an existing pending transaction. Recovery state is
    written atomically by LKSU core before any one-shot GRUB mutation.
    """
    from .core import save
    if state_path.exists():
        import json
        existing = json.loads(state_path.read_text())
        if existing.get("pending"):
            raise DebianKernelError("Prior kernel trial awaits verification")
    result = install_kernel(distro_id, running_release, flavor=flavor)
    state = {"pending": True, "backend": "debian-apt-grub",
             "distribution": distro_id, "old_kernel": result["previous"],
             "new_default": "/boot/vmlinuz-" + result["candidate"],
             "trial_entry": None, "installed_package": result["package"],
             "rebooted": False}
    save(state_path, state)
    return state


def stage_managed_trial(state_path):
    """Persist trial intent first; GRUB next_entry is not a durable rollback plan."""
    import json
    from .core import save
    state = json.loads(state_path.read_text())
    if state.get("backend") != "debian-apt-grub" or not state.get("pending"):
        raise DebianKernelError("No pending Debian-family kernel transaction")
    if state.get("trial_entry"):
        raise DebianKernelError("Trial already staged")
    release = state["new_default"].removeprefix("/boot/vmlinuz-")
    if not RELEASE.fullmatch(release) or not RELEASE.fullmatch(state["old_kernel"]):
        raise DebianKernelError("Invalid persisted kernel state")
    images = boot_images()
    if release not in images or state["old_kernel"] not in images:
        raise DebianKernelError("Rollback or trial boot image missing")
    entry = grub_menu_entry(release)
    old_entry = grub_menu_entry(state["old_kernel"])
    if entry == old_entry:
        raise DebianKernelError("Trial and rollback entries must differ")
    # The current kernel must remain the persistent fallback. Never stage a
    # one-shot boot unless the saved GRUB default resolves to the old kernel.
    try:
        default = subprocess.run(["grub-editenv", "list"], capture_output=True,
                                 text=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DebianKernelError("Cannot inspect persistent GRUB boot state") from exc
    if default.returncode or ("saved_entry=" + old_entry) not in default.stdout.splitlines():
        raise DebianKernelError("Persistent GRUB default is not the preserved old kernel")
    result = stage_one_shot(release)
    state["trial_entry"] = entry
    save(state_path, state)
    return {**result, "old_kernel": state["old_kernel"]}


def verify_managed(state_path, running_release, healthy):
    """Confirm boot health; keep state pending on failure for operator recovery."""
    import json
    from .core import save
    state = json.loads(state_path.read_text())
    if state.get("backend") != "debian-apt-grub" or not state.get("pending"):
        raise DebianKernelError("No pending Debian-family kernel transaction")
    target = state["new_default"].removeprefix("/boot/vmlinuz-")
    success = bool(healthy) and running_release == target
    if success:
        # A successful trial must become the persistent default; otherwise
        # GRUB will boot the previous kernel again on the following reboot.
        entry = state.get("trial_entry")
        if not entry:
            raise DebianKernelError("No recorded trial GRUB entry to promote")
        try:
            promoted = subprocess.run(["grub-set-default", entry], check=False, timeout=30)
            current = subprocess.run(["grub-editenv", "list"], capture_output=True,
                                     text=True, check=False, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DebianKernelError("Cannot promote verified kernel in GRUB") from exc
        if promoted.returncode or current.returncode or (
                "saved_entry=" + entry) not in current.stdout.splitlines():
            raise DebianKernelError("Verified kernel was not confirmed as GRUB default")
        state["pending"] = False
        state["last_known_good"] = running_release
        save(state_path, state)
    return {"healthy": success, "running": running_release,
            "old_kernel": state["old_kernel"],
            "status": "verified" if success else "operator-recovery-required"}
