"""Conservative /boot reclamation before an authorized kernel update.

Never prune a running/default kernel, the newest two installed kernel-core
releases, or an LKSU-tracked rollback kernel. Do not use 'remove --oldinstallonly':
its policy can remove more than one fallback at once.
"""
import json
import os
import shutil

from . import core

MIN_BOOT_FREE = 150 * 1024 * 1024
KERNEL_RPM_NAMES = (
    "kernel", "kernel-core", "kernel-modules",
    "kernel-modules-core", "kernel-modules-extra",
)


def _kernel_core_install_times():
    query = core.run(
        "rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}.%{ARCH} %{INSTALLTIME}\\n",
        "kernel-core",
    ).stdout
    result = {}
    for line in query.splitlines():
        fields = line.split()
        if len(fields) != 2 or not core.VERSION.fullmatch(fields[0]) or not fields[1].isdigit():
            raise core.LKSUError("Cannot safely interpret installed kernel RPM metadata")
        release, epoch = fields
        if not release.endswith("." + os.uname().machine) or release in result:
            raise core.LKSUError("Ambiguous kernel RPM architecture or duplicate version")
        result[release] = int(epoch)
    if not result:
        raise core.LKSUError("No kernel-core RPMs found; refusing cleanup")
    return result


def _protected_releases(installed):
    running = os.uname().release
    default_path = core.default_kernel()
    default = default_path.removeprefix("/boot/vmlinuz-")
    if running not in installed or default != running:
        raise core.LKSUError(
            "Automatic kernel cleanup requires the running kernel to be the GRUB default"
        )
    if core.pending_update() is not None:
        raise core.LKSUError("Cannot clean kernels while a reboot is pending verification")
    # Keep the two most recently installed kernels irrespective of lexical ordering.
    newest = sorted(installed, key=lambda release: (installed[release], release))[-2:]
    protected = set(newest) | {running, default}
    if core.STATE.exists():
        try:
            state = json.loads(core.STATE.read_text())
        except (OSError, ValueError) as exc:
            raise core.LKSUError("Invalid LKSU kernel state; refusing cleanup") from exc
        if not isinstance(state, dict):
            raise core.LKSUError("Invalid LKSU kernel state; refusing cleanup")
        for field in ("old_kernel", "last_known_good"):
            value = state.get(field)
            if value is not None:
                if not isinstance(value, str) or not core.VERSION.fullmatch(value):
                    raise core.LKSUError("Invalid rollback kernel state; refusing cleanup")
                protected.add(value)
    return protected


def _exact_installed_packages(release):
    targets = []
    for name in KERNEL_RPM_NAMES:
        full_name = name + "-" + release
        response = core.run(
            "rpm", "-q", "--qf", "%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\\n",
            full_name, check=False,
        )
        if response.returncode == 1:
            continue
        if response.returncode != 0 or response.stdout.splitlines() != [full_name]:
            raise core.LKSUError("Unexpected kernel package match; refusing cleanup")
        targets.append(full_name)
    if "kernel-core-" + release not in targets:
        raise core.LKSUError("Selected kernel has no matching core package")
    return targets


def reclaim_for_update(target_free_bytes=MIN_BOOT_FREE):
    """Return removed kernel releases; run under LKSU kernel_operation_lock.

    Called only after eligible updates have been identified, and only when
    /boot free space is below the installation guard threshold. A dependency
    test and exact-NEVRA package targeting fail closed on nonstandard hosts.
    """
    if os.geteuid():
        raise core.LKSUError("Root required for kernel cleanup")
    removed = []
    while shutil.disk_usage("/boot").free < target_free_bytes:
        versions = _kernel_core_install_times()
        protected = _protected_releases(versions)
        if len(versions) <= 2:
            raise core.LKSUError(
                "Insufficient /boot space; only two installed kernels remain. "
                "No more automatic cleanup is permitted."
            )
        candidates = sorted(
            (release for release in versions if release not in protected),
            key=lambda release: (versions[release], release),
        )
        if not candidates:
            raise core.LKSUError(
                "Insufficient /boot space; all remaining kernels are protected"
            )
        release = candidates[0]
        packages = _exact_installed_packages(release)
        # rpm --test refuses an erase that would break installed dependencies.
        # DNF's auto-removal is disabled so no unrelated packages are pruned.
        core.run("rpm", "-e", "--test", *packages, timeout=120)
        core.run(
            "dnf", "-y", "--setopt=clean_requirements_on_remove=False",
            "--setopt=installonly_limit=0", "remove", *packages, timeout=900,
        )
        remaining = set(core.installed())
        if release in remaining or os.uname().release not in remaining:
            raise core.LKSUError("Kernel cleanup postcondition failed; inspect RPM state")
        if core.default_kernel() != "/boot/vmlinuz-" + os.uname().release:
            raise core.LKSUError("Kernel cleanup changed the GRUB default; inspect boot state")
        if len(remaining) < 2:
            raise core.LKSUError("Kernel cleanup unexpectedly removed the fallback kernel")
        removed.append(release)
    return removed


def prune_verified_kernels():
    """Prune obsolete releases only after successful post-boot verification.

    Preserve the running/default kernel, the newest two releases, and any
    recorded rollback release. Caller must hold the kernel operation lock.
    """
    if os.geteuid():
        raise core.LKSUError("Root required for kernel cleanup")
    removed = []
    while True:
        versions = _kernel_core_install_times()
        protected = _protected_releases(versions)
        candidates = sorted(
            (release for release in versions if release not in protected),
            key=lambda release: (versions[release], release),
        )
        if not candidates:
            return removed
        release = candidates[0]
        packages = _exact_installed_packages(release)
        core.run("rpm", "-e", "--test", *packages, timeout=120)
        core.run(
            "dnf", "-y", "--setopt=clean_requirements_on_remove=False",
            "--setopt=installonly_limit=0", "remove", *packages, timeout=900,
        )
        remaining = set(core.installed())
        if release in remaining or os.uname().release not in remaining:
            raise core.LKSUError("Kernel cleanup postcondition failed")
        if core.default_kernel() != "/boot/vmlinuz-" + os.uname().release:
            raise core.LKSUError("Kernel cleanup changed GRUB default")
        if len(remaining) < 2:
            raise core.LKSUError("Kernel cleanup removed the fallback kernel")
        removed.append(release)
