"""Debian-family kernel package discovery and GRUB entry planning.

This module performs no host mutations on import. Installation and reboot
are deliberately separate operations so callers can persist rollback state.
"""
import pathlib
import re
import subprocess

RELEASE = re.compile(r"^[A-Za-z0-9._+~-]+$")


class DebianKernelError(RuntimeError):
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
