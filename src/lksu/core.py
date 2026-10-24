"""Host checks and state transitions. No shell interpolation or implicit reboot."""
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

PACKAGES = ("kernel", "kernel-core", "kernel-modules", "kernel-modules-core", "kernel-modules-extra")
STATE = Path("/var/lib/lksu/state.json")
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


def preflight():
    version = os_version()
    for binary in ("dnf", "rpm", "grubby", "findmnt", "systemctl"):
        if not shutil.which(binary):
            raise LKSUError(f"Required command missing: {binary}")
    if os.geteuid() != 0:
        raise LKSUError("Root required")
    if run("findmnt", "-n", "-o", "OPTIONS", "/boot", check=False).returncode == 0:
        pass  # /boot may also be part of /; disk_usage handles either layout.
    boot = shutil.disk_usage("/boot")
    if boot.free < 500 * 1024 * 1024:
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
    info = preflight()
    info["updates"] = updates()
    from .policy import security_advisories
    info["security_advisories"] = security_advisories()
    return info


def apply(policy):
    if policy not in {"all-stable", "security-only"}:
        raise LKSUError("Installation requires policy=all-stable or security-only")
    before = check()
    if policy == "security-only" and not before["security_advisories"]:
        return {"status": "no-security-updates", **before}
    if not before["updates"]:
        return {"status": "no-updates", **before}
    if STATE.exists() and json.loads(STATE.read_text()).get("pending"):
        raise LKSUError("Prior update still awaits post-boot verification")
    old = before["running"]
    # Preserve the exact running kernel and its installed modules against DNF's installonly cleanup.
    # DNF installonly_limit is overridden for this transaction; never erase old RPMs here.
    command = ["dnf", "-y", "--setopt=installonly_limit=0", "upgrade"]
    if policy == "security-only":
        command.append("--security")
    run(*command, *PACKAGES)
    after = installed()
    if old not in after or not Path(f"/boot/vmlinuz-{old}").exists():
        raise LKSUError("Old kernel disappeared; inspect host before reboot")
    chosen = default_kernel()
    if chosen == f"/boot/vmlinuz-{old}":
        raise LKSUError("New kernel was not selected as default; inspect DNF result")
    state = {"pending": True, "old_kernel": old, "new_default": chosen, "installed": after, "updated_at": int(time.time())}
    save(STATE, state)
    return {"status": "installed-awaiting-manual-reboot", **state}


def verify(cfg):
    if not STATE.exists():
        raise LKSUError("No pending update")
    state = json.loads(STATE.read_text())
    if not state.get("pending"):
        raise LKSUError("No pending update")
    running = os.uname().release
    from .health import check_all
    results = check_all(cfg)
    healthy = running == state["new_default"].removeprefix("/boot/vmlinuz-") and all(results.values())
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
    old_image = f"/boot/vmlinuz-{state['old_kernel']}"
    new_image = state["new_default"]
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
