"""Plain-text English reports for operators; unknown states are never marked healthy."""
import json
import os
import socket
from datetime import datetime
from pathlib import Path

from . import core


def _os_name():
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "Not available"


def _installed_kernels():
    try:
        return core.installed()
    except (core.LKSUError, OSError, ValueError):
        return None


def _rollback_status(installed_kernels, result):
    old = result.get("old_kernel")
    if not old:
        try:
            if core.STATE.exists():
                state = json.loads(core.STATE.read_text())
                old = state.get("old_kernel")
        except (OSError, ValueError, TypeError, AttributeError):
            return "Unknown (saved update state could not be read)"
    if not old:
        return "No previous kernel recorded by LKSU; provider snapshot not checked"
    if not isinstance(old, str) or not core.VERSION.fullmatch(old):
        return "Unknown (invalid saved kernel identifier)"
    image = Path("/boot/vmlinuz-" + old)
    if installed_kernels is None:
        return old + " (installed package status not checked)"
    if old in installed_kernels and image.is_file():
        return old + " (RPM and boot image present; recovery boot not tested)"
    return old + " (rollback availability NOT verified: RPM or boot image missing)"


def _window_description(cfg):
    window = cfg.get("maintenance_window")
    if not isinstance(window, dict) or window.get("enabled", True) is False:
        return "Disabled"
    if not window:
        return "Not configured"
    start = window.get("start")
    duration = window.get("duration_minutes", 60)
    if start is None:
        return "Incomplete configuration"
    return "Daily at {} server local time ({} minutes)".format(start, duration)


def _outcome(command, result):
    status = result.get("status")
    updates = result.get("updates")
    if status == "initial-run-completed":
        return "ALREADY INITIALIZED", "The first kernel installation pass was already completed earlier; no installation or reboot repeated.", "Routine monitoring and maintenance timers continue."
    if status == "initial-check-only":
        return "CHECK ONLY", "Initial kernel assessment completed; automatic kernel installation was not authorized.", "Enable automatic installation explicitly to install future kernel updates."
    if status == "error":
        return "ERROR", "Command failed; results must not be treated as a successful check.", "Yes - investigate the error shown below."
    if status == "self-updated":
        return "LKSU UPDATED", "LKSU application upgraded to a verified release without reboot.", "Monitor the next scheduled health and kernel checks."
    if status == "self-update-available":
        return "LKSU UPDATE AVAILABLE", "A newer LKSU application release is published; no installation was performed.", "Review the published release."
    if status == "self-update-current":
        return "LKSU CURRENT", "Installed LKSU application release is current.", "No action indicated."
    if status == "self-update-no-release":
        return "NO LKSU RELEASE", "No stable GitHub release is published; LKSU was not modified.", "No action indicated."
    if status == "self-update-disabled":
        return "SELF-UPDATE DISABLED", "Automatic LKSU application updates are disabled by configuration.", "No action indicated."
    if status == "no-pending-verification":
        return "NOT REQUIRED", "There is no pending LKSU kernel transition to verify.", "No action indicated."
    if status == "verification-pending":
        return "VERIFICATION PENDING", "A kernel transition is pending post-boot verification; no further kernel installation was attempted.", "Yes - check the booted kernel and run lksu verify."
    if status == "trial-boot-staged":
        return "TRIAL BOOT STAGED", "One-shot trial boot was staged; the previous kernel remains the persistent fallback.", "Monitor host access and complete post-boot health verification."
    if result.get("reboot_required"):
        return "REBOOT REQUIRED", "The default boot kernel is installed but differs from the running kernel; no further package upgrade is necessarily needed.", "Review the boot target and execute a guarded trial reboot in an approved maintenance window."
    if status == "outside-maintenance-window":
        if isinstance(updates, list) and updates:
            return "DEFERRED", "Read-only kernel check completed; installation skipped outside the maintenance window.", "Review available updates; installation is deferred until an authorized window."
        if isinstance(updates, list):
            return "SKIPPED", "Read-only kernel check found no available package upgrades; maintenance action skipped.", "No immediate action indicated by this check."
        return "SKIPPED", "Maintenance action skipped outside the configured window; update availability was not checked.", "Review the scheduled daily check before drawing conclusions."
    if status == "installed-awaiting-manual-reboot":
        return "REBOOT PENDING", "Kernel packages installed; the running kernel has not yet been verified after reboot.", "Yes - arrange a controlled reboot and run lksu verify after boot."
    if status == "no-security-updates":
        return "NO SECURITY UPDATES", "No eligible security advisories found in the available DNF metadata; no installation.", "No immediate action indicated; keep checking for advisories."
    if status == "no-updates":
        return "NO UPDATES", "No kernel package upgrades found in enabled repositories.", "No immediate action indicated."
    if "healthy" in result:
        if result["healthy"]:
            return "VERIFIED", "Post-boot service and kernel verification passed.", "No immediate action indicated."
        return "ACTION REQUIRED", "Post-boot verification failed; the update remains pending.", "Yes - investigate failed checks and confirm console access before any rollback."
    if result.get("alerts"):
        return "SECURITY ALERT", "Security Watch reported findings that require investigation.", "Yes - review each finding and host audit logs."
    if command == "stage-reboot":
        return "TRIAL BOOT STAGED", "One-shot trial boot was staged; this message does not prove a reboot occurred.", "Yes - confirm recovery access and review reboot policy."
    if command == "security-check" and status == "ok":
        return "SECURITY OK", "No Security Watch findings were reported.", "No action indicated by Security Watch."
    if command == "scheduled" or command == "check":
        if isinstance(updates, list) and updates:
            return "UPDATES AVAILABLE", "Kernel updates are available; this read-only check made no changes.", "Yes - review eligible packages and plan an authorized update."
        if isinstance(updates, list):
            return "NO UPDATES", "No kernel package upgrades found in enabled repositories.", "No immediate action indicated."
    return "COMPLETED", "LKSU command returned without an error.", "Review the details below."


def build_email_report(cfg, command, result, *, timestamp=None, hostname=None, os_name=None, installed_kernels=None):
    """Return (subject, plaintext); optional arguments allow deterministic unit tests.

    installed_kernels=None means query the local RPM DB; an empty list means an
    actual empty result. The format never presents an unknown update state as 0.
    """
    if timestamp is None:
        timestamp = datetime.now().astimezone()
    if hostname is None:
        hostname = socket.gethostname()
    if os_name is None:
        os_name = _os_name()
    if installed_kernels is None:
        installed_kernels = _installed_kernels()
    level, summary, action = _outcome(command, result)
    updates = result.get("updates")
    advisories = result.get("security_advisories")
    package_count = str(len(updates)) if isinstance(updates, list) else "Not checked"
    advisory_items = [a for a in advisories if isinstance(a, dict) and a.get("id")] if isinstance(advisories, list) else []
    advisory_count = str(len(advisory_items)) if isinstance(advisories, list) else "Not checked"

    lines = [
        "LKSU | Linux Kernel Security Updater",
        "=" * 42,
        "",
        "Summary",
        "-------",
        "Result: " + level,
        "Operation: " + command,
        "Details: " + summary,
        "Action required: " + action,
        "",
        "Server",
        "------",
        "Hostname: " + str(hostname),
        "Operating system: " + str(os_name),
        "Report time: " + timestamp.isoformat(timespec="seconds"),
        "Running kernel: " + str(result.get("running") or os.uname().release),
        "Installed kernels: " + (", ".join(installed_kernels) if installed_kernels else ("None found" if installed_kernels == [] else "Not available")),
        "Default kernel: " + str(result.get("default", "Not checked")),
        "Boot status: " + str(result.get("boot_status", "Not checked")),
        "Reboot required: " + ("Yes" if result.get("reboot_required") is True else ("No" if result.get("reboot_required") is False else "Not determined")),
        "Reboot target: " + str(result.get("reboot_target") or result.get("new_default") or "Not established"),
        "Rollback kernel: " + _rollback_status(installed_kernels, result),
        "",
        "Update assessment",
        "-----------------",
        "Kernel package upgrades: " + package_count,
        "Security advisories: " + advisory_count,
        "Advisory applicability: Not confirmed by this count alone",
        "Install policy: " + str(cfg.get("policy", "Not configured")),
        "Automatic installation: " + ("Enabled" if cfg.get("automatic_updates", False) else "Disabled"),
        "Automatic reboot: " + ("Enabled" if cfg.get("automatic_reboot", False) else "Disabled"),
        "Recovery readiness approval: " + ("Confirmed by operator" if cfg.get("recovery_ready") else "Not confirmed"),
        "Automatic LKSU application updates: " + ("Enabled" if cfg.get("automatic_lksu_updates") else "Disabled"),
        "",
        "Scheduling",
        "----------",
        "Maintenance window: " + _window_description(cfg),
        "Maintenance action: " + ("Skipped - outside maintenance window" if result.get("status") == "outside-maintenance-window" else "See operation and result above"),
        "Next scheduled check: Not determined here; inspect systemctl list-timers on the host.",
    ]
    if isinstance(updates, list) and updates:
        lines.extend(["", "Available kernel packages", "-------------------------"])
        for item in updates[:30]:
            if isinstance(item, dict):
                lines.append("- {} {} ({})".format(item.get("name", "?"), item.get("evr", "?"), item.get("arch", "?")))
        if len(updates) > 30:
            lines.append("- ... {} additional packages".format(len(updates) - 30))
    if advisory_items:
        lines.extend(["", "Security advisories", "-------------------"])
        for item in advisory_items[:5]:
            cves = item.get("cves") or []
            cve_text = ", ".join(str(v) for v in cves[:3]) if isinstance(cves, list) and cves else "CVEs not listed"
            if isinstance(cves, list) and len(cves) > 3:
                cve_text += " (+{} more CVEs)".format(len(cves) - 3)
            lines.append("- {} | {} | {}".format(item.get("id"), item.get("severity", "Unknown"), cve_text))
        if len(advisory_items) > 5:
            lines.append("- ... {} additional advisories; use lksu check --json for details".format(len(advisory_items) - 5))
    if isinstance(advisories, list):
        for item in advisories:
            if isinstance(item, dict) and item.get("warning"):
                lines.append("Advisory warning: " + str(item["warning"])[:300])
    if result.get("status", "").startswith("self-update"):
        lines.extend(["", "LKSU application", "----------------",
            "Installed application version: " + str(result.get("installed_version", "Not checked")),
            "Available release: " + str(result.get("release_version", "Not checked"))])
    if result.get("error"):
        lines.extend(["", "Failure details", "---------------", str(result["error"])[:1000]])
    if "services" in result and isinstance(result["services"], dict):
        lines.extend(["", "Post-boot health checks", "-----------------------"])
        for name, passed in sorted(result["services"].items()):
            lines.append("- {}: {}".format(name, "PASS" if passed else "FAIL"))
    if isinstance(result.get("alerts"), list) and result["alerts"]:
        lines.extend(["", "Security findings", "-----------------"])
        for alert in result["alerts"][:20]:
            if isinstance(alert, dict):
                lines.append("- {} [{}]: {}".format(alert.get("code", "?"), alert.get("severity", "?"), str(alert.get("message", ""))[:200]))
    lines.extend(["", "Important: A preserved kernel is not a VM snapshot or a proven rollback. Confirm provider-console recovery before reboot.", ""])
    subject = "LKSU [{}] {} | {}".format(level, hostname, command)
    return subject, "\n".join(lines)


def format_console_report(cfg, command, result):
    """Human-readable, bounded English output; --json retains complete details."""
    level, summary, action = _outcome(command, result)
    def display(value):
        return str(value) if value is not None else "Not checked"

    lines = [
        "",
        "LKSU | Linux Kernel Security Updater",
        "-" * 42,
        "Host:             " + os.uname().nodename,
        "Operation:        " + command,
        "Status:           " + level,
        "Summary:          " + summary,
    ]
    running = result.get("running")
    if running:
        lines.append("Running kernel:   " + str(running))
    target = result.get("reboot_target") or result.get("new_default") or result.get("default")
    if target:
        lines.append("Next boot kernel: " + str(target).removeprefix("/boot/vmlinuz-"))
    required = result.get("reboot_required")
    if required is not None:
        lines.append("Reboot required:  " + ("Yes" if required else "No"))
    upgrades = result.get("updates")
    if isinstance(upgrades, list):
        lines.append("Package upgrades: " + str(len(upgrades)) + " available")
    advisories = result.get("security_advisories")
    if isinstance(advisories, list):
        count = sum(bool(isinstance(a, dict) and a.get("id")) for a in advisories)
        lines.append("Advisories:       " + str(count) + " listed (not proof of unpatched CVEs)")
    if result.get("status", "").startswith("self-update"):
        if result.get("installed_version"):
            lines.append("LKSU installed:   " + display(result.get("installed_version")))
        if result.get("release_version"):
            lines.append("Latest release:   " + display(result.get("release_version")))
    if command in {"initialize", "check", "scheduled", "maintenance", "apply", "stage-reboot"}:
        lines.append("Kernel updates:   " + ("Enabled" if cfg.get("automatic_updates") else "Disabled"))
        lines.append("Automatic reboot: " + ("Enabled (subject to safety checks)" if cfg.get("automatic_reboot") else "Disabled"))
        lines.append("Maintenance:      " + _window_description(cfg))
    lines.append("LKSU self-update: " + ("Enabled" if cfg.get("automatic_lksu_updates") else "Disabled"))
    if result.get("error"):
        lines.append("Error:            " + str(result["error"])[:500])
    lines.append("Next action:      " + action)
    lines.append("Full technical details: lksu " + command + " --json")
    lines.append("")
    return "\n".join(lines)
