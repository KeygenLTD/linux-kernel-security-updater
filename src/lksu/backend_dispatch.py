"""Select only verified distro-specific kernel backend capabilities.

This dispatcher deliberately imports no foreign package-management backends.
Unverified platforms are never allowed to run AlmaLinux DNF/GRUB operations.
"""
from .distributions import detect, require_automatic_kernel_backend


def backend_plan(distro=None):
    distro = distro or detect()
    if distro.identifier == "almalinux" and distro.version.split(".", 1)[0] in ("8", "9", "10"):
        require_automatic_kernel_backend(distro)
        return {"distribution": distro.identifier, "version": distro.version,
                "backend": "almalinux-rpm-grub", "package_manager": "dnf",
                "automatic_kernel_install": True, "guarded_trial_reboot": True}
    return {"distribution": distro.identifier, "version": distro.version,
            "backend": None, "package_manager": distro.package_manager,
            "automatic_kernel_install": False, "guarded_trial_reboot": False,
            "reason": distro.reason}
