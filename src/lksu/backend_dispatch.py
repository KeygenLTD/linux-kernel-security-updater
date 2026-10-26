"""Report kernel backend capabilities without assuming cross-distro compatibility.

Only the validated AlmaLinux implementation may perform automatic mutations.
The Debian QEMU kernel exercise is an independent test harness, not an LKSU
backend. Never advertise it as a production capability.
"""
from .distributions import detect, require_automatic_kernel_backend


def backend_plan(distro=None):
    distro = distro or detect()
    validated = distro.identifier == "almalinux" and distro.version.split(".", 1)[0] in ("8", "9", "10")
    if validated:
        require_automatic_kernel_backend(distro)
        return {"distribution": distro.identifier, "version": distro.version,
                "backend": "almalinux-rpm-grub", "package_manager": "dnf",
                "automatic_kernel_install": True, "guarded_trial_reboot": True,
                "verification": "AlmaLinux-specific implementation"}
    return {"distribution": distro.identifier, "version": distro.version,
            "backend": None, "package_manager": distro.package_manager,
            "automatic_kernel_install": False, "guarded_trial_reboot": False,
            "verification": "not validated for automatic kernel mutation",
            "reason": distro.reason}


def require_mutation_backend(distro=None):
    """Fail closed before any kernel package transaction or reboot."""
    plan = backend_plan(distro)
    if not plan["automatic_kernel_install"] or not plan["guarded_trial_reboot"]:
        from .core import LKSUError
        raise LKSUError(
            "Automatic kernel update and rollback are unavailable on "
            + plan["distribution"] + " " + plan["version"] + ": "
            + plan.get("reason", "backend not verified")
        )
    return plan
