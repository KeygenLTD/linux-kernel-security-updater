"""Read-only native package inventory for Linux hosts outside AlmaLinux.

This module NEVER installs kernels, edits GRUB, or triggers reboots. Kernel
package candidate metadata is not evidence of a safe upgrade or patched CVEs.
"""
import re

from . import core
from .distributions import detect

DEBIAN_KERNEL = re.compile(r"^linux-image-(?:[0-9][a-zA-Z0-9.+_~-]*|generic|virtual|aws|azure|gcp|lowlatency|rt|cloud-[a-z0-9-]+)$")
RPM_KERNEL = re.compile(r"^(?:kernel(?:-[a-z0-9-]+)?|kernel-uek|kernel-lt|kernel-ml)$")
SAFE_PACKAGE = re.compile(r"^[a-zA-Z0-9.+_~-]+$")


def _installed_apt_images():
    proc = core.run("dpkg-query", "-W", "-f=${binary:Package} ${Status} ${Version}\n",
                    "linux-image-*", check=False, timeout=40)
    if proc.returncode not in (0, 1):
        raise core.LKSUError("Could not query installed APT kernel packages: " + proc.stderr[:250])
    images = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) != 5 or not parts[0].startswith("linux-image-"):
            continue
        name, want, error, status, version = parts
        if (want, error, status) != ("install", "ok", "installed"):
            continue
        if not DEBIAN_KERNEL.fullmatch(name) or not SAFE_PACKAGE.fullmatch(version):
            continue
        images.append({"name": name, "version": version})
    return images


def apt_inventory(distro):
    if distro.family != "debian":
        raise core.LKSUError("APT inventory requires Debian-family distribution")
    running = core.os.uname().release
    images = _installed_apt_images()
    # Do NOT guess which kernel meta-package or flavor the operator uses.
    return {"distribution": distro.identifier, "version": distro.version,
            "running_kernel": running, "installed_kernel_packages": images,
            "automatic_updates": "blocked", "automatic_reboot": "blocked",
            "note": "Read-only APT inventory; no safe kernel upgrade/rollback backend yet"}


def rpm_inventory(distro):
    if distro.package_manager != "dnf/rpm":
        raise core.LKSUError("RPM inventory requires RPM-family distribution")
    proc = core.run("rpm", "-qa", "--qf", "%{NAME} %{VERSION}-%{RELEASE}.%{ARCH}\n",
                    check=False, timeout=40)
    if proc.returncode != 0:
        raise core.LKSUError("Could not query installed RPM packages: " + proc.stderr[:250])
    kernels = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        name, release = parts
        if RPM_KERNEL.fullmatch(name) and SAFE_PACKAGE.fullmatch(release):
            kernels.append({"name": name, "version": release})
    return {"distribution": distro.identifier, "version": distro.version,
            "running_kernel": core.os.uname().release,
            "installed_kernel_packages": kernels,
            "automatic_updates": "blocked", "automatic_reboot": "blocked",
            "note": "Read-only RPM inventory; vendor modules and boot path not validated"}


def inventory():
    distro = detect()
    if distro.family == "debian":
        return apt_inventory(distro)
    if distro.package_manager == "dnf/rpm" and distro.identifier != "almalinux":
        return rpm_inventory(distro)
    return {"distribution": distro.identifier, "version": distro.version,
            "automatic_updates": "blocked", "automatic_reboot": "blocked",
            "note": "No inventory backend available; platform detection only"}
