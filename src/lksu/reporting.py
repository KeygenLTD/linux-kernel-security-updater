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


def _outcome(command, result):
    status = result.get("status")
    updates = result.get("updates")
    if status == "reboot-blocked":
        return ("REBOOT BLOCKED",
                "A new kernel is installed or ready for boot, but unattended reboot was blocked by safety checks.",
                "Yes - " + str(result.get("reboot_block_reason", "inspect recovery preflight"))[:240])
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
        return "REBOOT REQUIRED", "The default boot kernel is installed but differs from the running kernel; no further package upgrade is necessarily needed.", "Review the boot target and allow a guarded trial reboot when authorized by configuration."
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
    """Concise, outcome-focused email. Unknown states are never called successful."""
    if timestamp is None:
        timestamp = datetime.now().astimezone()
    if hostname is None:
        hostname = socket.gethostname()
    server = str(cfg.get("display_name") or hostname)
    tr = str(cfg.get("report_language", "en")).lower() == "tr"
    status = result.get("status")
    verified = command == "verify" and result.get("healthy") is True and result.get("verification_performed") is not False
    failed_verify = command == "verify" and result.get("healthy") is False and result.get("verification_performed") is not False
    error = status in {"error", "reboot-blocked"}
    manual = status == "installed-awaiting-manual-reboot"
    if verified:
        heading = "Güncelleme Başarılı" if tr else "Update Successful"
        detail = "Yeni kernel doğrulandı ve sağlık kontrolleri başarılı." if tr else "New kernel verified; health checks passed."
        action = "İşlem gerekmiyor." if tr else "No action required."
    elif failed_verify:
        heading = "Müdahale Gerekiyor" if tr else "Action Required"
        detail = "Yeniden başlatma sonrası doğrulama başarısız. Güncelleme tamamlanmış sayılmaz." if tr else "Post-boot verification failed. Update is not confirmed complete."
        action = "Başarısız servisleri ve kurtarma erişimini kontrol edin." if tr else "Check failed services and recovery access."
    elif manual:
        heading = "Müdahale Gerekiyor" if tr else "Action Required"
        detail = "Kernel kuruldu ancak yeni kernel henüz çalışırken doğrulanmadı." if tr else "Kernel installed but not yet verified while running."
        action = "Güvenli yeniden başlatma ve ardından doğrulama gerekiyor." if tr else "Controlled reboot and subsequent verification required."
    elif error:
        heading = "Güncelleme Yapılamadı" if tr else "Update Failed"
        detail = str(result.get("error") or result.get("reboot_block_reason") or ("Bilinmeyen hata" if tr else "Unknown failure"))[:500]
        action = "Sunucu durumunu kontrol edin; otomatik tekrar deneme doğrulanmadı." if tr else "Check server status; automatic retry not confirmed."
    elif status == "self-updated":
        heading = "LKSU Güncellendi" if tr else "LKSU Updated"
        detail = str(result.get("installed_version") or ("Sürüm belirtilmedi" if tr else "Version not reported"))
        action = "İşlem gerekmiyor." if tr else "No action required."
    else:
        heading = "İşlem Durumu Belirsiz" if tr else "Operation Status Unknown"
        detail = str(status or "unknown")
        action = "Teknik kayıtları kontrol edin." if tr else "Review technical logs."
    lines = [
        "LKSU | " + heading,
        "",
        ("Sunucu: " if tr else "Server: ") + server,
        ("Sonuç: " if tr else "Result: ") + detail,
    ]
    old = result.get("old_kernel")
    new = result.get("running") if verified else result.get("new_default") or result.get("reboot_target")
    if old:
        lines.append(("Önceki kernel: " if tr else "Previous kernel: ") + str(old))
    if new:
        lines.append(("Yeni kernel: " if tr else "New kernel: ") + str(new))
    services = result.get("services")
    if isinstance(services, dict):
        bad = [str(name) for name, ok in services.items() if not ok]
        if bad:
            lines.append(("Başarısız kontroller: " if tr else "Failed checks: ") + ", ".join(bad[:12]))
    lines.extend([
        "",
        ("Yapılması gereken: " if tr else "Next action: ") + action,
        ("Tarih: " if tr else "Time: ") + timestamp.isoformat(timespec="seconds"),
        "",
    ])
    return "LKSU | {} | {}".format(heading, server), "\n".join(lines)


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
        lines.append("Kernel checks:    Every 15 minutes (24/7 timer)")
    lines.append("LKSU self-update: " + ("Enabled" if cfg.get("automatic_lksu_updates") else "Disabled"))
    if isinstance(result.get("cleaned_old_kernels"), list) and result["cleaned_old_kernels"]:
        lines.append("Old kernels cleaned: " + ", ".join(
            str(release)[:100] for release in result["cleaned_old_kernels"][:10]
        ))
    if result.get("reboot_block_reason"):
        lines.append("Reboot blocked:   " + str(result["reboot_block_reason"])[:500])
    if result.get("error"):
        lines.append("Error:            " + str(result["error"])[:500])
    lines.append("Next action:      " + action)
    lines.append("Full technical details: lksu " + command + " --json")
    lines.append("")
    return "\n".join(lines)
