"""Plain-text English reports for operators; unknown states are never marked healthy."""
import json
import os
import socket
from datetime import datetime
from pathlib import Path

from . import core



# Translation is applied only to presentation; kernel IDs, service names,
# errors, advisory identifiers and machine-readable JSON remain unchanged.
_TR = {
    "Summary": "Özet", "Server": "Sunucu", "Update assessment": "Güncelleme değerlendirmesi",
    "Scheduling": "Zamanlama", "Old kernel cleanup": "Eski kernel temizliği",
    "Available kernel packages": "Mevcut kernel paketleri",
    "Security advisories": "Güvenlik duyuruları",
    "LKSU application": "LKSU uygulaması",
    "Reboot safety block": "Yeniden başlatma güvenlik engeli",
    "Failure details": "Hata ayrıntıları",
    "Post-boot health checks": "Açılış sonrası sağlık kontrolleri",
    "Security findings": "Güvenlik bulguları",
    "Result": "Sonuç", "Operation": "İşlem", "Details": "Ayrıntılar",
    "Action required": "Gerekli işlem", "Hostname": "Sunucu adı",
    "Operating system": "İşletim sistemi", "Report time": "Rapor zamanı",
    "Running kernel": "Çalışan kernel", "Installed kernels": "Kurulu kerneller",
    "Default kernel": "Varsayılan kernel", "Boot status": "Açılış durumu",
    "Reboot required": "Yeniden başlatma gerekli",
    "Reboot target": "Yeniden başlatma hedefi", "Rollback kernel": "Geri dönüş kerneli",
    "Kernel package upgrades": "Kernel paket güncellemeleri",
    "Security advisories": "Güvenlik duyuruları",
    "Advisory applicability": "Duyuru geçerliliği",
    "Install policy": "Kurulum politikası",
    "Automatic installation": "Otomatik kurulum",
    "Automatic reboot": "Otomatik yeniden başlatma",
    "Recovery readiness approval": "Kurtarma hazırlığı onayı",
    "Automatic LKSU application updates": "Otomatik LKSU güncellemeleri",
    "Kernel check interval": "Kernel kontrol aralığı",
    "Automatic kernel installation": "Otomatik kernel kurulumu",
    "Unattended reboot": "Gözetimsiz yeniden başlatma",
    "Next scheduled check": "Sonraki zamanlanmış kontrol",
    "Installed application version": "Kurulu uygulama sürümü",
    "Available release": "Mevcut sürüm",
    "Advisory warning": "Duyuru uyarısı",
    "Host": "Sunucu", "Status": "Durum", "Next boot kernel": "Sonraki açılış kerneli",
    "Package upgrades": "Paket güncellemeleri", "Advisories": "Duyurular",
    "LKSU installed": "Kurulu LKSU", "Latest release": "Son sürüm",
    "Kernel updates": "Kernel güncellemeleri", "Kernel checks": "Kernel kontrolleri",
    "LKSU self-update": "LKSU otomatik güncelleme",
    "Old kernels cleaned": "Temizlenen eski kerneller",
    "Reboot blocked": "Yeniden başlatma engellendi",
    "Error": "Hata", "Next action": "Sonraki işlem",
    "Full technical details": "Tüm teknik ayrıntılar",
    "VERIFIED": "DOĞRULANDI", "NO UPDATES": "GÜNCELLEME YOK",
    "NO SECURITY UPDATES": "GÜVENLİK GÜNCELLEMESİ YOK",
    "ERROR": "HATA", "ACTION REQUIRED": "İŞLEM GEREKLİ",
    "REBOOT BLOCKED": "YENİDEN BAŞLATMA ENGELLENDİ",
    "REBOOT REQUIRED": "YENİDEN BAŞLATMA GEREKLİ",
    "REBOOT PENDING": "YENİDEN BAŞLATMA BEKLENİYOR",
    "TRIAL BOOT STAGED": "DENEME AÇILIŞI HAZIR",
    "LKSU UPDATED": "LKSU GÜNCELLENDİ",
    "ALREADY INITIALIZED": "ZATEN BAŞLATILDI",
    "CHECK ONLY": "YALNIZCA KONTROL",
    "NOT REQUIRED": "GEREKMİYOR", "VERIFICATION PENDING": "DOĞRULAMA BEKLENİYOR",
    "COMPLETED": "TAMAMLANDI", "SECURITY ALERT": "GÜVENLİK UYARISI",
    "Enabled": "Etkin", "Disabled": "Devre dışı", "Not checked": "Kontrol edilmedi",
    "Not available": "Mevcut değil", "Not determined": "Belirlenmedi",
    "Not established": "Belirlenmedi", "Yes": "Evet", "No": "Hayır",
    "PASS": "BAŞARILI", "FAIL": "BAŞARISIZ",
}
_TR_PHRASES = {
    "Post-boot service and kernel verification passed.": "Açılış sonrası servis ve kernel doğrulaması başarılı.",
    "No immediate action indicated.": "Şu anda işlem gerekmiyor.",
    "No kernel package upgrades found in enabled repositories.": "Etkin depolarda kernel güncellemesi bulunamadı.",
    "Kernel packages installed; the running kernel has not yet been verified after reboot.": "Kernel paketleri kuruldu; yeniden başlatma sonrası doğrulama bekleniyor.",
    "Post-boot verification failed; the update remains pending.": "Açılış sonrası doğrulama başarısız; güncelleme beklemede.",
    "Command failed; results must not be treated as a successful check.": "Komut başarısız; sonuçlar başarılı kontrol olarak değerlendirilmemeli.",
    "Yes - investigate the error shown below.": "Evet - aşağıdaki hatayı inceleyin.",
    "Yes - investigate failed checks and confirm console access before any rollback.": "Evet - başarısız kontrolleri inceleyin ve geri dönüş öncesinde konsol erişimini doğrulayın.",
    "No previous kernel recorded by LKSU; provider snapshot not checked": "LKSU önceki kernel kaydetmemiş; sağlayıcı snapshot'ı kontrol edilmedi",
    "Unknown (saved update state could not be read)": "Bilinmiyor (kayıtlı güncelleme durumu okunamadı)",
    "Unknown (invalid saved kernel identifier)": "Bilinmiyor (geçersiz kayıtlı kernel kimliği)",
    "None found": "Bulunamadı", "Not configured": "Yapılandırılmadı",
    "Confirmed by operator": "Operatör tarafından onaylandı",
    "Not confirmed": "Onaylanmadı",
    "Every 15 minutes (24/7, when timer is enabled)": "Her 15 dakikada (zamanlayıcı etkinken 7/24)",
    "Every 15 minutes (24/7 timer)": "Her 15 dakikada (7/24)",
    "Requires automatic_updates and eligible policy": "automatic_updates ve uygun kurulum politikası gerektirir",
    "Requires opt-in and passing recovery/health checks": "Onay ve başarılı kurtarma/sağlık kontrolleri gerektirir",
    "Not determined here; inspect systemctl list-timers on the host.": "Burada belirlenmedi; sunucuda systemctl list-timers komutunu inceleyin.",
    "Not confirmed by this count alone": "Yalnızca bu sayı ile doğrulanamaz",
    "Important: A preserved kernel is not a VM snapshot or a proven rollback. Confirm provider-console recovery before reboot.": "Önemli: Korunan kernel VM snapshot'ı veya doğrulanmış geri dönüş değildir. Yeniden başlatmadan önce sağlayıcı konsolundan kurtarmayı doğrulayın.",
}
_TR_PHRASES.update({
    "installed package status not checked": "kurulu paket durumu kontrol edilmedi",
    "RPM and boot image present; recovery boot not tested": "RPM ve açılış dosyası mevcut; kurtarma açılışı test edilmedi",
    "rollback availability NOT verified: RPM or boot image missing": "geri dönüş kullanılabilirliği DOĞRULANAMADI: RPM veya açılış dosyası eksik",
    "No action indicated.": "İşlem gerekmiyor.",
    "Review the details below.": "Aşağıdaki ayrıntıları inceleyin.",
    "No immediate action indicated; keep checking for advisories.": "Şu anda işlem gerekmiyor; güvenlik duyurularını kontrol etmeye devam edin.",
    "No eligible security advisories found in the available DNF metadata; no installation.": "DNF verilerinde uygun güvenlik duyurusu bulunamadı; kurulum yapılmadı.",
    "LKSU command returned without an error.": "LKSU komutu hata olmadan tamamlandı.",
    "A kernel transition is pending post-boot verification; no further kernel installation was attempted.": "Kernel geçişinin açılış sonrası doğrulaması bekleniyor; yeni kurulum denenmedi.",
    "Yes - check the booted kernel and run lksu verify.": "Evet - çalışan kerneli kontrol edin ve lksu verify çalıştırın.",
    "The default boot kernel is installed but differs from the running kernel; no further package upgrade is necessarily needed.": "Varsayılan açılış kerneli kurulu ancak çalışan kernelden farklı; yeni paket kurulumu gerekmeyebilir.",
    "Review the boot target and allow a guarded trial reboot when authorized by configuration.": "Açılış hedefini inceleyin; yapılandırma izin veriyorsa korumalı deneme açılışı yapın.",
    "Kernel packages installed; the running kernel has not yet been verified after reboot.": "Kernel paketleri kuruldu; yeniden başlatma sonrası çalışan kernel henüz doğrulanmadı.",
    "Yes - arrange a controlled reboot and run lksu verify after boot.": "Evet - kontrollü yeniden başlatma planlayın ve açılıştan sonra lksu verify çalıştırın.",
    "One-shot trial boot was staged; the previous kernel remains the persistent fallback.": "Tek seferlik deneme açılışı hazırlandı; önceki kernel kalıcı geri dönüş seçeneği olarak korundu.",
    "Monitor host access and complete post-boot health verification.": "Sunucu erişimini izleyin ve açılış sonrası sağlık doğrulamasını tamamlayın.",
    "A new kernel is installed or ready for boot, but unattended reboot was blocked by safety checks.": "Yeni kernel kurulu veya açılışa hazır; gözetimsiz yeniden başlatma güvenlik kontrollerince engellendi.",
    "Routine monitoring and maintenance timers continue.": "Düzenli izleme ve bakım zamanlayıcıları çalışmaya devam ediyor.",
    "Enabled (subject to safety checks)": "Etkin (güvenlik kontrollerine bağlı)",
    "Every 15 minutes (24/7 timer)": "Her 15 dakikada (7/24 zamanlayıcı)",
})
_TR_COMMANDS = {
    "verify": "doğrulama", "check": "kontrol", "scheduled": "zamanlanmış kontrol",
    "maintenance": "bakım", "apply": "kurulum", "initialize": "başlatma",
    "stage-reboot": "deneme açılışını hazırlama", "self-update": "LKSU güncelleme",
    "self-update-check": "LKSU güncelleme kontrolü", "self-update-scheduled": "zamanlanmış LKSU güncellemesi",
    "security-check": "güvenlik kontrolü", "security-baseline": "güvenlik temel kaydı",
    "select-old": "eski kerneli seçme",
}
_TR_EXTRA = {
    "available": "mevcut", "listed (not proof of unpatched CVEs)": "listelendi (yamasız CVE kanıtı değildir)",
    "Removed obsolete kernel RPMs": "Eski kernel RPM paketleri kaldırıldı",
}

def _translate_line(line):
    if line in _TR_PHRASES:
        return _TR_PHRASES[line]
    if line in _TR:
        return _TR[line]
    if ":" in line:
        head, tail = line.split(":", 1)
        key = head.strip()
        if key in _TR:
            tail = tail.strip()
            tail = _TR_PHRASES.get(tail, _TR.get(tail, _TR_COMMANDS.get(tail, tail)))
            if key == "Package upgrades" and tail.endswith(" available"):
                tail = tail[:-len(" available")] + " mevcut"
            elif key == "Advisories" and tail.endswith(" listed (not proof of unpatched CVEs)"):
                tail = tail[:-len(" listed (not proof of unpatched CVEs)")] + " kayıt listelendi (yamalanmamış CVE bulunduğu anlamına gelmez)"
            else:
                for english, turkish in _TR_PHRASES.items():
                    if tail.endswith(" (" + english + ")"):
                        tail = tail[:-len(english) - 1] + turkish + ")"
                        break
            return _TR[key] + ": " + tail
    for english, turkish in _TR_EXTRA.items():
        if line.startswith("- " + english + ":"):
            return line.replace(english, turkish, 1)
    return line


def _localize_report(cfg, subject, body):
    language = cfg.get("report_language", "en")
    if language not in {"tr", "en"}:
        raise core.LKSUError("Invalid report_language; expected tr or en")
    if language == "en":
        return subject, body
    for english, turkish in _TR.items():
        subject = subject.replace("[" + english + "]", "[" + turkish + "]")
    return subject, "\n".join(_translate_line(line) for line in body.split("\n"))

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
    """Return (subject, plaintext); optional arguments allow deterministic unit tests.

    installed_kernels=None means query the local RPM DB; an empty list means an
    actual empty result. The format never presents an unknown update state as 0.
    """
    if timestamp is None:
        timestamp = datetime.now().astimezone()
    if hostname is None:
        hostname = socket.gethostname()
    hostname = cfg.get("display_name") or hostname
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
        "Kernel check interval: Every 15 minutes (24/7, when timer is enabled)",
        "Automatic kernel installation: Requires automatic_updates and eligible policy",
        "Unattended reboot: Requires opt-in and passing recovery/health checks",
        "Next scheduled check: Not determined here; inspect systemctl list-timers on the host.",
    ]
    removed = result.get("cleaned_old_kernels")
    if isinstance(removed, list) and removed:
        lines.extend(["", "Old kernel cleanup", "------------------"])
        for release in removed[:10]:
            lines.append("- Removed obsolete kernel RPMs: " + str(release)[:120])
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
    if result.get("reboot_block_reason"):
        lines.extend(["", "Reboot safety block", "-------------------", str(result["reboot_block_reason"])[:600]])
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
    return _localize_report(cfg, subject, "\n".join(lines))


def format_console_report(cfg, command, result):
    """Human-readable, bounded English output; --json retains complete details."""
    level, summary, action = _outcome(command, result)
    def display(value):
        return str(value) if value is not None else "Not checked"

    lines = [
        "",
        "LKSU | Linux Kernel Security Updater",
        "-" * 42,
        "Host:             " + (cfg.get("display_name") or os.uname().nodename),
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
    return _localize_report(cfg, "", "\n".join(lines))[1]
