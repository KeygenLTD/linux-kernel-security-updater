import argparse
import getpass
import json
from importlib.metadata import PackageNotFoundError, version as package_version
import os
import re
import smtplib
import ssl
import sys
from datetime import datetime
from email.message import EmailMessage

from . import core
from .fleet import send_report as send_fleet_report
from .reporting import build_email_report, format_console_report
from .security import check as security_check, create_baseline
from . import self_update, notifications
from .progress import event



_TR_UI = {
  "Report email: ": "Rapor e-posta adresi: ",
  "Mail provider [postmark/smtp2go/custom] (default postmark): ": "E-posta sağlayıcısı [postmark/smtp2go/custom] (varsayılan postmark): ",
  "Postmark Server Token: ": "Postmark sunucu anahtarı: ",
  "SMTP2GO username: ": "SMTP2GO kullanıcı adı: ",
  "SMTP2GO password: ": "SMTP2GO parolası: ",
  "SMTP host: ": "SMTP sunucusu: ",
  "SMTP port [465]: ": "SMTP portu [465]: ",
  "SMTP username: ": "SMTP kullanıcı adı: ",
  "SMTP password or app password: ": "SMTP parolası veya uygulama parolası: ",
  "Install available kernel updates on setup and automatically thereafter?": "Kurulumda ve sonrasında kernel güncellemeleri otomatik kurulsun mu?",
  "Automatically install verified LKSU releases?": "Doğrulanmış LKSU sürümleri otomatik kurulsun mu?",
  "Email only when updates succeed or fail?": "Yalnızca güncelleme başarılı veya başarısız olduğunda e-posta gönderilsin mi?",
  "Automatically reboot after installing a kernel when recovery checks pass?": "Kurtarma kontrolleri başarılıysa kernel kurulumundan sonra otomatik yeniden başlatılsın mı?",
  "Services to verify after reboot (comma-separated; Enter to detect running apps): ": "Yeniden başlatma sonrası kontrol edilecek servisler (virgülle ayırın; çalışanları algılamak için Enter): ",
  "HTTP/HTTPS health URLs (comma separated, optional): ": "HTTP/HTTPS sağlık kontrolü adresleri (virgülle ayırın, isteğe bağlı): ",
  "Automatically install kernel updates?": "Kernel güncellemeleri otomatik kurulsun mu?",
  "Automatically reboot after eligible kernel updates?": "Uygun kernel güncellemelerinden sonra otomatik yeniden başlatılsın mı?",
  "Kernel install policy [security-only/all-stable] (default all-stable): ": "Kernel kurulum politikası [security-only/all-stable] (varsayılan all-stable): ",
  "Services to check before and after reboot (comma separated, Enter to keep suggestions; 'none' for URL-only): ": "Yeniden başlatma öncesi ve sonrası kontrol edilecek servisler (virgülle ayırın; öneriler için Enter; yalnızca URL için 'none'): ",
  "Have you verified a current external snapshot AND provider console recovery?": "Güncel harici snapshot VE sağlayıcı konsolundan kurtarmayı doğruladınız mı?",
  "Have you verified an external snapshot AND provider console recovery?": "Harici snapshot VE sağlayıcı konsolundan kurtarmayı doğruladınız mı?",
  "Automatically install verified LKSU application releases? [Y/n]: ": "Doğrulanmış LKSU sürümleri otomatik kurulsun mu? [E/h]: ",
  "Root required": "Root yetkisi gerekli",
  "Automatic reboot requires at least one configured service or URL health check. No reboot configuration was saved.": "Otomatik yeniden başlatma için en az bir servis veya URL sağlık kontrolü gereklidir. Yapılandırma kaydedilmedi.",
  "Automatic kernel installation requires security-only or all-stable": "Otomatik kernel kurulumu için security-only veya all-stable politikası gerekir.",
  "Invalid report_language; expected tr or en": "Geçersiz rapor dili; tr veya en olmalıdır.",
  "Invalid email address": "Geçersiz e-posta adresi",
  "Invalid mail provider": "Geçersiz e-posta sağlayıcısı",
  "Invalid mail configuration": "Geçersiz e-posta yapılandırması",
  "Invalid install policy": "Geçersiz kurulum politikası",
  "Invalid service name": "Geçersiz servis adı",
  "Answer y or n": "Evet için e, hayır için h girin",
  "Automatic reboot is blocked until recovery readiness is confirmed.": "Kurtarma hazırlığı doğrulanana kadar otomatik yeniden başlatma engellenir.",
  "Kernel automation preferences saved; SMTP and recovery settings preserved.": "Kernel otomasyon tercihleri kaydedildi; SMTP ve kurtarma ayarları korundu.",
  "24/7 kernel checks: every 15 minutes. Install and guarded reboot require their configured opt-ins.": "Kernel kontrolleri 7/24 her 15 dakikada yapılır. Kurulum ve korumalı yeniden başlatma için izin gerekir.",
  "Enabled": "Etkin",
  "Disabled": "Devre dışı",
  "Current reboot health checks: ": "Mevcut yeniden başlatma sağlık kontrolleri: ",
  "Configured reboot health checks: ": "Yapılandırılan yeniden başlatma sağlık kontrolleri: ",
  "Detected running application services: ": "Algılanan çalışan uygulama servisleri: ",
  "Selected running application health checks: ": "Seçilen çalışan uygulama sağlık kontrolleri: "
}
_UI_LANG = 'en'
def _ui(message):
    return _TR_UI.get(message, message) if _UI_LANG == 'tr' else message

def _ui_input(message):
    return input(_ui(message))

def _ui_error(message):
    return core.LKSUError(_ui(message))

def _set_ui_language(value):
    global _UI_LANG
    _UI_LANG = value if value in ('tr', 'en') else 'en'

def yes_no(prompt, default):
    suffix = ("E/h" if default else "e/H") if _UI_LANG == "tr" else ("Y/n" if default else "y/N")
    value = input(f"{_ui(prompt)} [{suffix}]: ").strip().lower()
    if not value:
        return default
    if value not in {"y", "yes", "n", "no", "e", "evet", "h", "hayır", "hayir"}:
        raise _ui_error("Answer y or n")
    return value in {"y", "yes", "e", "evet"}


def detect_active_host_services():
    """Discover running, boot-enabled application services without panel assumptions.

    This is an onboarding suggestion, not proof of application health.
    Never auto-select base OS services just to satisfy a reboot gate.
    """
    units = core.run(
        "systemctl", "list-units", "--type=service", "--state=running",
        "--no-legend", "--plain", "--no-pager",
    ).stdout
    os_services = {
        "auditd", "chronyd", "crond", "dbus", "dbus-broker",
        "firewalld", "irqbalance", "network", "networkmanager",
        "polkit", "qemu-guest-agent", "rsyslog", "sshd", "sssd",
        "tuned", "smartd", "rngd", "getty", "systemd-logind",
        "unattended-upgrades", "upower",
    }
    candidates = []
    for line in units.splitlines():
        fields = line.split()
        if not fields:
            continue
        unit = fields[0].lstrip("●")
        if not re.fullmatch(r"[A-Za-z0-9_.@-]+\.service", unit):
            continue
        name = unit[:-len(".service")]
        if (name.lower() in os_services
                or name.startswith(("systemd-", "lksu-", "user@", "getty@", "serial-getty@", "dbus-"))):
            continue
        candidates.append((unit, name))
    enabled_services = []
    for unit, name in sorted(set(candidates))[:80]:
        result = core.run("systemctl", "is-enabled", unit, check=False)
        if result.returncode == 0 and result.stdout.strip() in {"enabled", "enabled-runtime"}:
            enabled_services.append(name)
    return enabled_services[:16]


def validate_reboot_health_checks(services, health_urls):
    if not services and not health_urls:
        raise _ui_error("Automatic reboot requires at least one configured service or URL health check. No reboot configuration was saved.")


def _language_label(lang):
    return "Türkçe" if lang == "tr" else "English"


def choose_report_language(current="tr"):
    """Choose report language; invalid answers never change saved configuration."""
    value = input(("Rapor ve arayüz dili [tr/en] (varsayılan {}): " if current == "tr" else "Report and interface language [tr/en] (default {}): ").format(current)).strip().lower() or current
    if value not in {"tr", "en"}:
        raise _ui_error("Dil tr veya en olmalıdır / Language must be tr or en")
    return value


def configure_language():
    """Change report language on an existing host without touching SMTP or automation."""
    if os.geteuid():
        raise _ui_error("Root required")
    cfg = core.config()
    cfg["report_language"] = choose_report_language(cfg.get("report_language", "en"))
    core.save(core.CONFIG, cfg)
    print(("Rapor ve arayüz dili kaydedildi: " if cfg["report_language"] == "tr" else "Report and interface language saved: ") + _language_label(cfg["report_language"]))


def setup():
    if os.geteuid():
        raise _ui_error("Root required")
    core.os_version()
    report_language = choose_report_language("tr")
    _set_ui_language(report_language)
    email = _ui_input("Report email: ").strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise _ui_error("Invalid email address")
    provider = _ui_input("Mail provider [postmark/smtp2go/custom] (default postmark): ").strip().lower() or "postmark"
    if provider == "postmark":
        host, port = "smtp.postmarkapp.com", 587
        token = getpass.getpass(_ui("Postmark Server Token: "))
        user = password = token
    elif provider == "smtp2go":
        host, port = "mail.smtp2go.com", 587
        user = _ui_input("SMTP2GO username: ").strip()
        password = getpass.getpass(_ui("SMTP2GO password: "))
    elif provider == "custom":
        host = _ui_input("SMTP host: ").strip()
        port = int(_ui_input("SMTP port [465]: ").strip() or "465")
        user = _ui_input("SMTP username: ").strip()
        password = getpass.getpass(_ui("SMTP password or app password: "))
    else:
        raise _ui_error("Invalid mail provider")
    if not user or not password or not re.fullmatch(r"[A-Za-z0-9.-]+", host):
        raise _ui_error("Invalid mail configuration")
    automatic_updates = yes_no("Install available kernel updates on setup and automatically thereafter?", True)
    automatic_lksu_updates = yes_no("Automatically install verified LKSU releases?", True)
    notify_events = yes_no("Email only when updates succeed or fail?", True)
    automatic_reboot = yes_no("Automatically reboot after installing a kernel when recovery checks pass?", True)
    default_policy = "all-stable" if automatic_updates else "check-only"
    policy = _ui_input(
        ("Kernel kurulum politikası" if _UI_LANG == "tr" else "Install policy") + f" [check-only/security-only/all-stable] ({'varsayılan' if _UI_LANG == 'tr' else 'default'} {default_policy}): "
    ).strip() or default_policy
    if automatic_updates and policy == "check-only":
        raise _ui_error("Automatic kernel installation requires security-only or all-stable")
    if policy not in {"check-only", "security-only", "all-stable"}:
        raise _ui_error("Invalid install policy")
    services = _ui_input("Services to verify after reboot (comma-separated; Enter to detect running apps): ").strip()
    parsed = [x.strip() for x in services.split(",") if x.strip()]
    if any(not re.fullmatch(r"[A-Za-z0-9_.@-]+", x) for x in parsed):
        raise _ui_error("Invalid service name")
    health_urls = _ui_input("HTTP/HTTPS health URLs (comma separated, optional): ").strip()
    parsed_urls = [{"url": x.strip(), "status": 200} for x in health_urls.split(",") if x.strip()]
    if automatic_reboot and not parsed and not parsed_urls:
        parsed = detect_active_host_services()
        if parsed:
            print(_ui("Selected running application health checks: ") + ", ".join(parsed))
    if automatic_reboot:
        validate_reboot_health_checks(parsed, parsed_urls)
    recovery_ready = False
    if automatic_reboot:
        print(_ui("Automatic reboot is blocked until recovery readiness is confirmed."))
        recovery_ready = yes_no("Have you verified an external snapshot AND provider console recovery?", False)
    core.save(core.CONFIG, {"report_language": report_language, "email": email, "from_email": email, "smtp_host": host, "smtp_port": port,
                            "smtp_user": user, "smtp_password": password, "policy": policy,
                            "services": parsed, "health_urls": parsed_urls,
                            "automatic_updates": automatic_updates, "automatic_lksu_updates": automatic_lksu_updates,
                            "recovery_ready": recovery_ready, "notifications": notify_events,
                            "automatic_reboot": automatic_reboot,
                            "security_watch": {"required_services": ["auditd", "firewalld"],
                                               "require_selinux_enforcing": True,
                                               "ssh_failure_threshold": 5,
                                               "watched_files": ["/etc/ssh/sshd_config", "/etc/sudoers"]}})
    print(f"Configuration saved; automatic reboot is {'enabled' if automatic_reboot else 'disabled'}.")
    print("Configuration only: kernel installation/reboot has NOT started. Run the bootstrap installer or 'lksu initialize' for the first managed update.")


def configure_automation():
    """Change kernel automation without overwriting SMTP or unrelated config."""
    if os.geteuid():
        raise _ui_error("Root required")
    cfg = core.config()
    _set_ui_language(cfg.get("report_language", "en"))
    update = yes_no("Automatically install kernel updates?", cfg.get("automatic_updates", False))
    reboot = yes_no("Automatically reboot after eligible kernel updates?", cfg.get("automatic_reboot", False))
    cfg["automatic_updates"] = update
    cfg["automatic_reboot"] = reboot
    cfg.pop("maintenance_window", None)  # Never reintroduce legacy scheduling restrictions.
    if update and cfg.get("policy") == "check-only":
        policy = _ui_input("Kernel install policy [security-only/all-stable] (default all-stable): ").strip() or "all-stable"
        if policy not in {"security-only", "all-stable"}:
            raise _ui_error("Invalid install policy")
        cfg["policy"] = policy
    if reboot:
        current_services = list(cfg.get("services") or [])
        if current_services:
            print(_ui("Current reboot health checks: ") + ", ".join(current_services))
            defaults = current_services
        else:
            defaults = detect_active_host_services()
            print(_ui("Detected running application services: ") + (", ".join(defaults) if defaults else "none"))
        names = _ui_input(
            "Services to check before and after reboot (comma separated, Enter to keep suggestions; 'none' for URL-only): "
        ).strip()
        parsed = (
            [] if names.lower() == "none" else
            [x.strip() for x in names.split(",") if x.strip()] if names else defaults
        )
        if any(not re.fullmatch(r"[A-Za-z0-9_.@-]+", x) for x in parsed):
            raise _ui_error("Invalid service name")
        cfg["services"] = parsed
        if parsed:
            print(_ui("Configured reboot health checks: ") + ", ".join(parsed))
        validate_reboot_health_checks(cfg.get("services"), cfg.get("health_urls"))
        cfg["recovery_ready"] = yes_no(
            "Have you verified a current external snapshot AND provider console recovery?",
            cfg.get("recovery_ready", False),
        )
    else:
        cfg["recovery_ready"] = False
    core.save(core.CONFIG, cfg)
    core.run("systemctl", "enable", "--now", "lksu-maintenance.timer")
    print(_ui("Kernel automation preferences saved; SMTP and recovery settings preserved."))
    print(_ui("24/7 kernel checks: every 15 minutes. Install and guarded reboot require their configured opt-ins."))



def configure_self_update():
    """Explicit one-time opt-in for an existing configuration, without resetting SMTP."""
    if os.geteuid():
        raise _ui_error("Root required")
    cfg = core.config()
    _set_ui_language(cfg.get("report_language", "en"))
    enabled = yes_no("Automatically install verified LKSU releases?", True)
    cfg["automatic_lksu_updates"] = enabled
    core.save(core.CONFIG, cfg)
    print(_ui("Automatic LKSU application updates: ") + _ui("Enabled" if enabled else "Disabled"))


def send_report(cfg, subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.get("from_email", cfg["email"])
    msg["To"] = cfg["email"]
    msg.set_content(body)
    context = ssl.create_default_context()
    if cfg["smtp_port"] == 465:
        with smtplib.SMTP_SSL(cfg["smtp_host"], 465, timeout=20, context=context) as smtp:
            smtp.login(cfg["smtp_user"], cfg["smtp_password"])
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(cfg["smtp_user"], cfg["smtp_password"])
            smtp.send_message(msg)


def _installed_version():
    try:
        return package_version("lksu")
    except PackageNotFoundError:
        return "unknown"


def _active_status(cfg):
    timer = core.run("systemctl", "is-active", "lksu-maintenance.timer", check=False)
    enabled = core.run("systemctl", "is-enabled", "lksu-maintenance.timer", check=False)
    running = timer.returncode == 0 and timer.stdout.strip() == "active"
    scheduled = enabled.returncode == 0 and enabled.stdout.strip() in {"enabled", "enabled-runtime"}
    return {
        "version": _installed_version(),
        "timer_active": running,
        "timer_enabled": scheduled,
        "automatic_updates": bool(cfg.get("automatic_updates", False)),
        "automatic_reboot": bool(cfg.get("automatic_reboot", False)),
        "self_update": bool(cfg.get("automatic_lksu_updates", False)),
        "report_language": cfg.get("report_language", "en"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="AlmaLinux Kernel Security Updater")
    parser.add_argument("--version", action="version", version="LKSU " + _installed_version())
    parser.add_argument("--json", action="store_true", help="Print the full machine-readable report instead of an operator summary")
    parser.add_argument("command", choices=("active", "compatibility", "kernel-inventory", "configure", "configure-automation", "configure-self-update", "configure-language", "initialize", "check", "scheduled", "apply", "maintenance", "stage-reboot", "verify", "select-old", "security-baseline", "security-check", "self-update", "self-update-check", "self-update-scheduled"))
    args = parser.parse_args(argv)
    reboot_requested = False
    mail_failure = None
    report_attempted = False
    cfg = None
    try:
        if args.command == "active":
            cfg = core.config()
            _set_ui_language(cfg.get("report_language", "en"))
            status = _active_status(cfg)
            if args.json:
                print(json.dumps(status, indent=2))
            else:
                healthy = status["timer_active"] and status["timer_enabled"]
                title = ("ETKİN" if healthy else "ETKİN DEĞİL") if _UI_LANG == "tr" else ("ACTIVE" if healthy else "INACTIVE")
                print(f"LKSU v{status['version']}: {title}")
                for key, label in [("timer_active", "Zamanlayıcı çalışıyor" if _UI_LANG == "tr" else "Timer active"), ("timer_enabled", "Zamanlayıcı etkin" if _UI_LANG == "tr" else "Timer enabled"), ("automatic_updates", "Otomatik kernel güncellemeleri" if _UI_LANG == "tr" else "Automatic kernel updates"), ("automatic_reboot", "Otomatik yeniden başlatma (güvenlik koşullu)" if _UI_LANG == "tr" else "Automatic reboot (guarded)"), ("self_update", "LKSU otomatik güncelleme" if _UI_LANG == "tr" else "LKSU self-update")]:
                    print(f"{label}: {('Evet' if status[key] else 'Hayır') if _UI_LANG == 'tr' else ('Yes' if status[key] else 'No')}")
            return 0
        if args.command == "compatibility":
            from .distributions import detect
            assessment = detect().as_dict()
            if args.json:
                print(json.dumps(assessment, indent=2))
            else:
                for key, value in assessment.items():
                    print(f"{key.replace('_', ' ').capitalize()}: {value}")
            return 0
        if args.command == "kernel-inventory":
            try:
                _set_ui_language(core.config().get("report_language", "en"))
            except (core.LKSUError, OSError, ValueError):
                _set_ui_language("en")
            from .kernel_inventory import inventory
            assessment = inventory()
            if args.json:
                print(json.dumps(assessment, indent=2))
            else:
                labels = {"distribution": "Dağıtım", "version": "Sürüm", "running_kernel": "Çalışan kernel", "installed_kernel_packages": "Kurulu kernel paketleri", "automatic_updates": "Otomatik güncellemeler", "automatic_reboot": "Otomatik yeniden başlatma", "note": "Not"}
                for key, value in assessment.items():
                    label = labels.get(key, key.replace("_", " ").capitalize()) if _UI_LANG == "tr" else key.replace("_", " ").capitalize()
                    if _UI_LANG == "tr" and value == "configured-separately":
                        value = "Ayrı yapılandırılır (lksu check)"
                    print(f"{label}: {value}")
            return 0
        if args.command == "configure":
            setup()
            return 0
        if args.command == "configure-language":
            configure_language()
            return 0
        if args.command == "configure-self-update":
            configure_self_update()
            return 0
        if args.command == "configure-automation":
            configure_automation()
            return 0
        cfg = core.config()
        _set_ui_language(cfg.get("report_language", "en"))
        if args.command == "initialize":
            with core.kernel_operation_lock():
                result, reboot_requested = core.initial_run(cfg)
        elif args.command == "self-update-check":
            result = self_update.check()
        elif args.command in {"self-update", "self-update-scheduled"}:
            result = self_update.update(automatic=args.command == "self-update-scheduled",
                                        enabled=cfg.get("automatic_lksu_updates", False))
        elif args.command == "security-baseline":
            if os.geteuid(): raise _ui_error("Root required")
            result = {"status": "baseline-created", "baseline": create_baseline(cfg)}
        elif args.command == "security-check":
            if os.geteuid(): raise _ui_error("Root required")
            result = security_check(cfg)
        elif args.command == "check":
            result = core.check()
        elif args.command == "apply":
            if os.geteuid():
                raise _ui_error("Root required")
            with core.kernel_operation_lock():
                result = core.apply(cfg["policy"])
        elif args.command == "scheduled":
            result = core.check()
        elif args.command == "maintenance":
            with core.kernel_operation_lock():
                result, reboot_requested = core.maintenance(cfg)
        elif args.command == "stage-reboot":
            with core.kernel_operation_lock():
                if cfg.get("automatic_reboot"):
                    core.auto_reboot_preflight(cfg)
                result = core.stage_trial_boot()
            if cfg.get("automatic_reboot"):
                reboot_requested = True
        elif args.command == "verify":
            with core.kernel_operation_lock():
                result = core.verify(cfg)
        else:
            if os.geteuid():
                raise _ui_error("Root required")
            with core.kernel_operation_lock():
                result = {"old_default": core.select_old(), "rebooted": False}
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(format_console_report(cfg, args.command, result))
        routine_reports = args.command in {"initialize", "scheduled", "apply", "maintenance", "stage-reboot", "verify", "self-update", "self-update-scheduled"}
        if reboot_requested:
            event("REBOOT", "Trial kernel prepared; sending event notification and recording fleet report before restart...")
        report_attempted = True
        try:
            notifications.send_event(cfg, args.command, result, send_report, build_email_report)
        except (core.LKSUError, OSError, ValueError, KeyError, smtplib.SMTPException) as mail_error:
            mail_failure = mail_error
            print(("LKSU olay e-postası gönderilemedi: " if _UI_LANG == "tr" else "LKSU event email delivery failed: ") + str(mail_error), file=sys.stderr)
        if routine_reports or args.command == "security-check":
            send_fleet_report(cfg, {"command": args.command, "result": result, "hostname": os.uname().nodename, "reported_at": int(datetime.now().timestamp())})
        if reboot_requested:
            target = str(result.get("new_default") or result.get("reboot_target") or "trial kernel").removeprefix("/boot/vmlinuz-")
            event("REBOOT", "Requesting system reboot NOW for one-time trial kernel " + target +
                  ". SSH may disconnect. Boot success is verified only after the server returns.")
            try:
                core.run("systemctl", "reboot")
            except core.LKSUError as exc:
                event("REBOOT", "Reboot request failed: " + str(exc))
                raise
            event("REBOOT", "systemctl accepted the reboot request. Waiting for server startup and post-boot checks.")
        if mail_failure is not None:
            return 1
        return 0 if not (args.command == "verify" and not result["healthy"]) else 2
    except (core.LKSUError, OSError, ValueError, KeyError, smtplib.SMTPException) as exc:
        print(("LKSU hatası: " if _UI_LANG == "tr" else "LKSU error: ") + str(exc), file=sys.stderr)
        # Report failed scheduled actions too, without retrying a failed SMTP send.
        if cfg is not None and not report_attempted and args.command in notifications.UPDATE_COMMANDS:
            try:
                notifications.send_event(cfg, args.command, {"status": "error", "error": str(exc)},
                                         send_report, build_email_report)
            except (core.LKSUError, OSError, ValueError, KeyError, smtplib.SMTPException) as mail_error:
                print(("LKSU rapor e-postası gönderilemedi: " if _UI_LANG == "tr" else "LKSU report delivery failed: ") + str(mail_error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
