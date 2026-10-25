"""Distribution compatibility discovery: no package changes or reboot side effects.

Never infer operational support from shared package managers alone. Backends are
activated only after distro-specific installation and recovery tests exist.
"""
from dataclasses import dataclass
from pathlib import Path

from .core import LKSUError


@dataclass(frozen=True)
class Distribution:
    identifier: str
    version: str
    family: str
    package_manager: str
    kernel_backend: str
    boot_backend: str
    update_capability: str
    reboot_capability: str
    reason: str

    def as_dict(self):
        return vars(self).copy()


def parse_os_release(content):
    data = {}
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, raw = stripped.split("=", 1)
        if not name.replace("_", "").isalnum():
            continue
        value = raw.strip()
        if value.startswith(('"', "'")) and value.endswith(value[0]):
            value = value[1:-1]
        data[name] = value
    return data


def detect(path=Path("/etc/os-release")):
    data = parse_os_release(path.read_text())
    identifier = data.get("ID", "").lower()
    version = data.get("VERSION_ID", "")
    major = version.split(".", 1)[0]
    if identifier == "almalinux" and major in {"8", "9", "10"}:
        return Distribution(identifier, version, "rhel", "dnf/rpm", "rpm-kernel",
                            "grubby/grub2-reboot", "enabled", "guarded",
                            "Existing LKSU AlmaLinux implementation")
    if identifier in {"rocky", "rhel", "centos", "fedora"}:
        return Distribution(identifier, version, "rhel", "dnf/rpm", "not-validated",
                            "not-validated", "not-validated", "blocked",
                            "RPM tools are similar, but kernel/GRUB lifecycle is not verified")
    if identifier in {"ubuntu", "debian"}:
        return Distribution(identifier, version, "debian", "apt/dpkg", "not-implemented",
                            "not-validated", "not-implemented", "blocked",
                            "APT kernel packaging and one-shot boot recovery require a dedicated backend")
    if identifier in {"arch", "manjaro"}:
        return Distribution(identifier, version, "arch", "pacman", "not-implemented",
                            "not-validated", "not-implemented", "blocked",
                            "Pacman kernel updates and boot recovery require separate implementation")
    return Distribution(identifier or "unknown", version, "unknown", "unknown",
                        "not-implemented", "not-validated", "unsupported", "blocked",
                        "Unrecognized distribution: do not update or reboot")


def require_automatic_kernel_backend(distro):
    """Safety gate: only explicitly validated distro+major combinations may mutate kernels."""
    if distro.update_capability != "enabled" or distro.reboot_capability != "guarded":
        raise LKSUError("Kernel automation is not supported on this distribution: " + distro.reason)
    return distro
