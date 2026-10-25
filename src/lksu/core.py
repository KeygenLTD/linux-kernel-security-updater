"""Host checks and state transitions. No shell interpolation or implicit reboot."""
import json
import fcntl
from contextlib import contextmanager
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

PACKAGES = ("kernel", "kernel-core", "kernel-modules", "kernel-modules-core", "kernel-modules-extra")
STATE = Path("/var/lib/lksu/state.json")
INITIAL_STATE = Path("/var/lib/lksu/initial-run.json")
KERNEL_LOCK = Path("/run/lock/lksu-kernel.lock")
CONFIG = Path("/etc/lksu/config.json")
VERSION = re.compile(r"^[A-Za-z0-9._+~-]+$")


class LKSUError(RuntimeError):
    pass


def run(*args, check=True, timeout=120):
    try:
        p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise LKSUError(f"{args[0]} timed out after {timeout}s; repository or network did not respond") from exc
    if check and p.returncode:
        raise LKSUError(f"{args[0]} exited {p.returncode}: {p.stderr.strip()[:500]}")
    return p


def os_version():
    data = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k] = v.strip('"')
    if data.get("ID") != "almalinux" or data.get("VERSION_ID", "").split(".")[0] not in {"8", "9", "10"}:
        raise LKSUError("Only AlmaLinux 8, 9 and 10 are supported")
    return data["VERSION_ID"]


def config():
    if not CONFIG.exists():
        raise LKSUError("Run 'lksu configure' first")
    if CONFIG.stat().st_mode & 0o077:
        raise LKSUError("Config must be readable only by root (chmod 600)")
    return json.loads(CONFIG.read_text())


def save(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(value, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def installed():
    p = run("rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}.%{ARCH}\n", "kernel-core")
    return sorted(set(p.stdout.splitlines()))


def default_kernel():
    value = run("grubby", "--default-kernel").stdout.strip()
    if not value.startswith("/boot/vmlinuz-"):
        raise LKSUError("Unexpected default boot entry")
    return value


def preflight(require_boot_space=True):
    version = os_version()
    for binary in ("dnf", "rpm", "grubby", "findmnt", "systemctl"):
        if not shutil.which(binary):
            raise LKSUError(f"Required command missing: {binary}")
    if os.geteuid() != 0:
        raise LKSUError("Root required")
    if run("findmnt", "-n", "-o", "OPTIONS", "/boot", check=False).returncode == 0:
        pass  # /boot may also be part of /; disk_usage handles either layout.
    boot = shutil.disk_usage("/boot")
    if require_boot_space and boot.free < 500 * 1024 * 1024:
        raise LKSUError("Less than 500 MiB free on /boot")
    if not Path("/boot/grub2/grub.cfg").exists() and not Path("/boot/efi/EFI/almalinux/grub.cfg").exists():
        raise LKSUError("GRUB configuration not found")
    running = os.uname().release
    if not VERSION.fullmatch(running) or not Path(f"/boot/vmlinuz-{running}").exists():
        raise LKSUError("Running kernel has no verified boot image")
    if running not in installed():
        raise LKSUError("Running kernel is not represented by an installed kernel-core RPM")
    return {"os": version, "running": running, "default": default_kernel(), "boot_free_mib": boot.free // 1048576}


def updates():
    # DNF exit 100 means updates available; repoquery output is package-specific and machine-readable.
    p = run("dnf", "-q", "repoquery", "--upgrades", "--qf", "%{name} %{evr} %{arch}", *PACKAGES, check=False)
    if p.returncode:
        raise LKSUError(f"DNF repoquery failed: {p.stderr.strip()[:500]}")
    found = []
    for line in p.stdout.splitlines():
        fields = line.split()
        if len(fields) != 3 or fields[0] not in PACKAGES or not all(VERSION.fullmatch(x) for x in fields):
            raise LKSUError("Unexpected DNF repoquery output")
        found.append({"name": fields[0], "evr": fields[1], "arch": fields[2]})
    return found


def check():
    # Read-only checks must remain available even if a future installation
    # needs kernel cleanup to recover sufficient /boot space.
    info = preflight(require_boot_space=False)
    info["updates"] = updates()
    from .policy import security_advisories
    info["security_advisories"] = security_advisories()
    info.update(boot_assessment(info))
    return info


def apply(policy):
    if policy not in {"all-stable", "security-only"}:
        raise LKSUError("Installation requires policy=all-stable or security-only")
    # Determine eligibility without treating low /boot as an unrecoverable error.
    before = check()
    if policy == "security-only" and not before["security_advisories"]:
        return {"status": "no-security-updates", **before}
    if not before["updates"]:
        return {"status": "no-updates", **before}
    if STATE.exists() and json.loads(STATE.read_text()).get("pending"):
        raise LKSUError("Prior update still awaits post-boot verification")
    old = before["running"]
    removed_old_kernels = []
    if before.get("boot_free_mib", 500) < 500:
        from .kernel_cleanup import reclaim_for_update
        removed_old_kernels = reclaim_for_update()
    # Validate free space, GRUB and the running kernel again before DNF.
    preflight()
    # Preserve the exact running kernel and its installed modules against DNF's installonly cleanup.
    # DNF installonly_limit is overridden for this transaction; never erase old RPMs here.
    command = ["dnf", "-y", "--setopt=installonly_limit=0", "upgrade"]
    if policy == "security-only":
        command.append("--security")
    run(*command, *PACKAGES, timeout=1800)
    after = installed()
    if old not in after or not Path(f"/boot/vmlinuz-{old}").exists():
        raise LKSUError("Old kernel disappeared; inspect host before reboot")
    chosen = default_kernel()
    if chosen == f"/boot/vmlinuz-{old}":
        raise LKSUError("New kernel was not selected as default; inspect DNF result")
    state = {"pending": True, "old_kernel": old, "new_default": chosen, "installed": after, "updated_at": int(time.time())}
    save(STATE, state)
    return {"status": "installed-awaiting-manual-reboot", **state,
            "cleaned_old_kernels": removed_old_kernels}


def verify(cfg):
    state = pending_update()
    if state is None:
        return {"status": "no-pending-verification", "healthy": True, "verification_performed": False}
    running = os.uname().release
    from .health import check_all
    results = check_all(cfg)
    healthy = bool(results) and running == state["new_default"].removeprefix("/boot/vmlinuz-") and all(results.values())
    report = {"healthy": healthy, "running": running, "services": results, "old_kernel": state["old_kernel"]}
    if healthy:
        run("grubby", "--set-default", state["new_default"])
        if default_kernel() != state["new_default"]:
            raise LKSUError("New kernel health passed but persistent default could not be verified")
        state["pending"] = False
        state["last_known_good"] = running
        save(STATE, state)
    else:
        report["recommended_action"] = "Investigate failed checks. If rollback is required, confirm provider console access, run 'lksu select-old', verify grubby --default-kernel, then reboot in an approved window."
    return report


def stage_trial_boot():
    """Keep old kernel persistent; select new kernel for one boot using GRUB next_entry."""
    if not STATE.exists():
        raise LKSUError("No pending update")
    state = json.loads(STATE.read_text())
    if not state.get("pending"):
        raise LKSUError("No pending update")
    if state.get("trial_entry"):
        raise LKSUError("Trial boot already staged; manual inspection required before retry")
    old_image = f"/boot/vmlinuz-{state['old_kernel']}"
    new_image = state["new_default"]
    available = installed()
    for image in (old_image, new_image):
        release = image.removeprefix("/boot/vmlinuz-")
        if not image.startswith("/boot/vmlinuz-") or not VERSION.fullmatch(release):
            raise LKSUError("Invalid saved kernel path; refusing boot changes")
        if release not in available or not Path(image).is_file():
            raise LKSUError(f"Kernel RPM or image missing: {release}")
        run("grubby", "--info", image)
    run("grubby", "--set-default", old_image)
    if default_kernel() != old_image:
        raise LKSUError("Could not preserve old kernel as persistent default")
    info = run("grubby", "--info", new_image).stdout
    entry = next((line.split("=", 1)[1].strip().strip('"') for line in info.splitlines() if line.startswith("id=")), None)
    if not entry or not re.fullmatch(r"[A-Za-z0-9._+~-]+", entry):
        raise LKSUError("Could not derive safe GRUB entry id for trial boot")
    if not shutil.which("grub2-reboot"):
        raise LKSUError("grub2-reboot is required for one-shot trial boot")
    run("grub2-reboot", entry)
    state["trial_entry"] = entry
    state["persistent_fallback"] = old_image
    save(STATE, state)
    return {"trial_entry": entry, "persistent_fallback": old_image, "rebooted": False}


def select_old():
    if not STATE.exists():
        raise LKSUError("No saved update state")
    old = json.loads(STATE.read_text())["old_kernel"]
    image = f"/boot/vmlinuz-{old}"
    if old not in installed() or not Path(image).exists():
        raise LKSUError("Old kernel is unavailable; no boot change made")
    run("grubby", "--set-default", image)
    if default_kernel() != image:
        raise LKSUError("Failed to verify old kernel as default")
    return image


@contextmanager
def kernel_operation_lock():
    """Prevent concurrent systemd timer and installer kernel modifications."""
    KERNEL_LOCK.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    with KERNEL_LOCK.open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LKSUError("Another LKSU kernel operation is running") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)



def pending_update():
    """Read an existing LKSU operation; never infer a completed rollback."""
    if not STATE.exists():
        return None
    state = json.loads(STATE.read_text())
    if not isinstance(state, dict):
        raise LKSUError("Invalid update state")
    return state if state.get("pending") else None


def boot_assessment(info):
    """Expose installed-but-not-running boot target without claiming an RPM upgrade."""
    current = info["running"]
    default = info["default"]
    candidate = default.removeprefix("/boot/vmlinuz-")
    if default == f"/boot/vmlinuz-{current}":
        return {"boot_status": "current", "reboot_required": False}
    if not default.startswith("/boot/vmlinuz-") or not VERSION.fullmatch(candidate):
        return {"boot_status": "unverified-default", "reboot_required": False}
    versions = installed()
    if candidate not in versions or not Path(default).is_file():
        return {"boot_status": "unverified-default", "reboot_required": False, "reboot_target": candidate}
    return {"boot_status": "different-installed-kernel", "reboot_required": True, "reboot_target": candidate}


def _is_newer_kernel(old, candidate):
    """Use AlmaLinux system RPM bindings even when LKSU runs in a private venv.

    LKSU's self-updater intentionally uses an isolated venv, where 'import rpm'
    normally fails. The distribution's /usr/bin/python3 has python3-rpm as an
    RPM dependency installed by LKSU's installer. Never approximate RPM EVR
    ordering using lexicographic or generic version sorting.
    """
    def evr(release):
        if not VERSION.fullmatch(release):
            raise LKSUError("Invalid kernel RPM release")
        reply = run("rpm", "-q", "--qf", "%{EPOCH} %{VERSION} %{RELEASE}\\n", "kernel-core-" + release)
        fields = reply.stdout.strip().split()
        if len(fields) != 3:
            raise LKSUError("Cannot determine installed kernel RPM version")
        epoch, version, build = fields
        if not VERSION.fullmatch(version) or not VERSION.fullmatch(build):
            raise LKSUError("Invalid kernel RPM EVR output")
        if epoch != "(none)" and not epoch.isdecimal():
            raise LKSUError("Invalid kernel RPM epoch")
        return ("0" if epoch == "(none)" else epoch, version, build)

    newer = evr(candidate)
    running = evr(old)
    python = Path("/usr/bin/python3")
    if not python.is_file():
        raise LKSUError("System Python missing at /usr/bin/python3; cannot compare RPM kernel versions")
    script = (
        "import rpm, sys; "
        "a=tuple(sys.argv[1:4]); b=tuple(sys.argv[4:7]); "
        "print(rpm.labelCompare(a,b))"
    )
    cmd = run(str(python), "-c", script, *newer, *running, check=False)
    if cmd.returncode:
        raise LKSUError(
            "System RPM version comparison failed (check 'dnf install python3-rpm'): "
            + cmd.stderr.strip()[:300]
        )
    if cmd.stdout.strip() not in {"-1", "0", "1"}:
        raise LKSUError("Unexpected RPM version comparison result; no boot changes made")
    return cmd.stdout.strip() == "1"


def adopt_preinstalled_kernel(info):
    """Record a separately installed NEWER default kernel; never install or reboot."""
    if pending_update() is not None:
        raise LKSUError("Existing pending update requires verification first")
    if not info.get("reboot_required") or info.get("boot_status") != "different-installed-kernel":
        raise LKSUError("No verified different installed boot target")
    old = info["running"]
    target = info["reboot_target"]
    if not _is_newer_kernel(old, target):
        raise LKSUError("Default kernel is not newer than running kernel; refusing unattended boot")
    for release in (old, target):
        image = f"/boot/vmlinuz-{release}"
        if release not in installed() or not Path(image).is_file():
            raise LKSUError("Kernel RPM or boot image unavailable: " + release)
        run("grubby", "--info", image)
    if not Path(f"/boot/initramfs-{target}.img").is_file():
        raise LKSUError("Target kernel initramfs is missing")
    state = {
        "pending": True, "old_kernel": old,
        "new_default": f"/boot/vmlinuz-{target}",
        "installed": installed(), "updated_at": int(time.time()),
        "source": "adopted-preinstalled-kernel",
    }
    save(STATE, state)
    return {"status": "installed-awaiting-manual-reboot", **state}


def auto_reboot_preflight(cfg):
    """Fail closed until human-approved recovery and meaningful health checks exist."""
    if not cfg.get("recovery_ready", False):
        raise LKSUError("Automatic reboot blocked: set recovery_ready=true only after confirming an external snapshot and provider-console recovery")
    if not cfg.get("services") and not cfg.get("health_urls"):
        raise LKSUError("Automatic reboot blocked: configure service or HTTP health checks first")
    from .health import check_all
    checks = check_all(cfg)
    if not checks or not all(checks.values()):
        raise LKSUError("Automatic reboot blocked: pre-reboot health checks failed")
    verify_unit = run("systemctl", "is-enabled", "lksu-verify.service", check=False)
    if verify_unit.returncode or verify_unit.stdout.strip() not in {"enabled", "enabled-runtime"}:
        raise LKSUError("Automatic reboot blocked: lksu-verify.service must be enabled")
    return checks


def maintenance(cfg):
    """Install eligible updates or safely adopt a pre-installed kernel at maintenance time."""
    state = pending_update()
    if state:
        result = check()
        result["status"] = "trial-boot-staged" if state.get("trial_entry") else "reboot-required"
        result["old_kernel"] = state.get("old_kernel")
        result["new_default"] = state.get("new_default")
        if result["running"] == state.get("new_default", "").removeprefix("/boot/vmlinuz-"):
            result["status"] = "verification-pending"
    elif cfg.get("automatic_updates") and cfg.get("policy") != "check-only":
        result = apply(cfg["policy"])
    else:
        result = check()
    if not cfg.get("automatic_reboot"):
        return result, False
    if result.get("status") in {"trial-boot-staged", "verification-pending"}:
        return result, False
    is_pending = result.get("status") == "reboot-required" or result.get("status") == "installed-awaiting-manual-reboot"
    adopt = result.get("reboot_required") and not is_pending
    if not is_pending and not adopt:
        return result, False
    try:
        auto_reboot_preflight(cfg)
    except LKSUError as exc:
        # Installation may already have completed; make the deferred reboot
        # visible rather than silently pretending the kernel is active.
        result["status"] = "reboot-blocked"
        result["reboot_block_reason"] = str(exc)
        return result, False
    if adopt:
        result = {**result, **adopt_preinstalled_kernel(result)}
    result["trial_boot"] = stage_trial_boot()
    result["status"] = "trial-boot-staged"
    return result, True


def initial_run(cfg):
    """Perform the first managed kernel update immediately after installer setup.

    This is the sole bypass for the recurring maintenance window. Explicit
    automatic_updates/automatic_reboot choices and reboot safety gates remain
    mandatory. Persist the completion marker before any requested reboot.
    """
    if INITIAL_STATE.exists():
        marker = json.loads(INITIAL_STATE.read_text())
        if marker.get("completed") is True:
            return {"status": "initial-run-completed", "completed_at": marker.get("completed_at")}, False
        raise LKSUError("Invalid initial-run state; inspect before retry")
    if not cfg.get("automatic_updates") and not cfg.get("automatic_reboot"):
        result = check()
        result["status"] = "initial-check-only"
        reboot = False
    else:
        result, reboot = maintenance(cfg)
    save(INITIAL_STATE, {
        "completed": True,
        "completed_at": int(time.time()),
        "result_status": result.get("status", "checked"),
        "reboot_requested": reboot,
    })
    return result, reboot
