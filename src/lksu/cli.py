import argparse
import getpass
import json
import os
import re
import smtplib
import ssl
import sys
from datetime import datetime
from email.message import EmailMessage

from . import core
from .fleet import send_report as send_fleet_report
from .policy import in_maintenance_window
from .reporting import build_email_report, format_console_report
from .security import check as security_check, create_baseline
from . import self_update, notifications


def yes_no(prompt, default):
    suffix = "Y/n" if default else "y/N"
    value = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not value:
        return default
    if value not in {"y", "yes", "n", "no"}:
        raise core.LKSUError("Answer y or n")
    return value in {"y", "yes"}


def detect_active_host_services():
    """Suggest only verified-active CyberPanel services; do not presume availability."""
    found = []
    for service in ("lsws", "mariadb", "lscpd"):
        status = core.run("systemctl", "is-active", "--quiet", service, check=False)
        if status.returncode == 0:
            found.append(service)
    return found


def validate_reboot_health_checks(services, health_urls):
    if not services and not health_urls:
        raise core.LKSUError(
            "Automatic reboot requires at least one configured service or URL health check. "
            "No reboot configuration was saved."
        )


def setup():
    if os.geteuid():
        raise core.LKSUError("Root required")
    core.os_version()
    email = input("Report email: ").strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise core.LKSUError("Invalid email address")
    provider = input("Mail provider [postmark/smtp2go/custom] (default postmark): ").strip().lower() or "postmark"
    if provider == "postmark":
        host, port = "smtp.postmarkapp.com", 587
        token = getpass.getpass("Postmark Server Token: ")
        user = password = token
    elif provider == "smtp2go":
        host, port = "mail.smtp2go.com", 587
        user = input("SMTP2GO username: ").strip()
        password = getpass.getpass("SMTP2GO password: ")
    elif provider == "custom":
        host = input("SMTP host: ").strip()
        port = int(input("SMTP port [465]: ").strip() or "465")
        user = input("SMTP username: ").strip()
        password = getpass.getpass("SMTP password or app password: ")
    else:
        raise core.LKSUError("Invalid mail provider")
    if not user or not password or not re.fullmatch(r"[A-Za-z0-9.-]+", host):
        raise core.LKSUError("Invalid mail configuration")
    automatic_updates = yes_no("Install available kernel updates on setup and automatically thereafter?", True)
    automatic_lksu_updates = yes_no("Automatically install verified LKSU releases?", True)
    notify_events = yes_no("Email only when updates succeed or fail?", True)
    automatic_reboot = yes_no("Automatically reboot after installing a kernel when recovery checks pass?", True)
    use_window = yes_no("Use a maintenance window for future kernel installations?", automatic_updates or automatic_reboot)
    start = input("Maintenance start [03:00]: ").strip() or "03:00" if use_window else "03:00"
    duration = int(input("Maintenance duration in minutes [60]: ").strip() or "60") if use_window else 60
    default_policy = "all-stable" if automatic_updates else "check-only"
    policy = input(
        f"Install policy [check-only/security-only/all-stable] (default {default_policy}): "
    ).strip() or default_policy
    if automatic_updates and policy == "check-only":
        raise core.LKSUError("Automatic kernel installation requires security-only or all-stable")
    if policy not in {"check-only", "security-only", "all-stable"}:
        raise core.LKSUError("Invalid install policy")
    services = input("Services to verify after reboot (comma separated, optional): ").strip()
    parsed = [x.strip() for x in services.split(",") if x.strip()]
    if any(not re.fullmatch(r"[A-Za-z0-9_.@-]+", x) for x in parsed):
        raise core.LKSUError("Invalid service name")
    health_urls = input("HTTP/HTTPS health URLs (comma separated, optional): ").strip()
    parsed_urls = [{"url": x.strip(), "status": 200} for x in health_urls.split(",") if x.strip()]
    if automatic_reboot and not parsed and not parsed_urls:
        parsed = detect_active_host_services()
        if parsed:
            print("Selected running server health checks: " + ", ".join(parsed))
    if automatic_reboot:
        validate_reboot_health_checks(parsed, parsed_urls)
    recovery_ready = False
    if automatic_reboot:
        print("Automatic reboot is blocked until recovery readiness is confirmed.")
        recovery_ready = yes_no("Have you verified an external snapshot AND provider console recovery?", False)
    core.save(core.CONFIG, {"email": email, "from_email": email, "smtp_host": host, "smtp_port": port,
                            "smtp_user": user, "smtp_password": password, "policy": policy,
                            "services": parsed, "health_urls": parsed_urls,
                            "automatic_updates": automatic_updates, "automatic_lksu_updates": automatic_lksu_updates,
                            "recovery_ready": recovery_ready, "notifications": notify_events,
                            "automatic_reboot": automatic_reboot,
                            "maintenance_window": {"enabled": use_window, "start": start, "duration_minutes": duration},
                            "security_watch": {"required_services": ["auditd", "firewalld"],
                                               "require_selinux_enforcing": True,
                                               "ssh_failure_threshold": 5,
                                               "watched_files": ["/etc/ssh/sshd_config", "/etc/sudoers"]}})
    print(f"Configuration saved; automatic reboot is {'enabled' if automatic_reboot else 'disabled'}.")


def configure_automation():
    """Change kernel automation without overwriting SMTP or unrelated config."""
    if os.geteuid():
        raise core.LKSUError("Root required")
    cfg = core.config()
    update = yes_no("Automatically install kernel updates?", cfg.get("automatic_updates", False))
    reboot = yes_no("Automatically reboot after eligible kernel updates?", cfg.get("automatic_reboot", False))
    window = dict(cfg.get("maintenance_window") or {})
    enabled = yes_no("Use a maintenance window for future updates?", window.get("enabled", True))
    start = window.get("start", "03:00")
    duration = window.get("duration_minutes", 60)
    if enabled:
        start = input(f"Maintenance start [{start}]: ").strip() or start
        duration = int(input(f"Maintenance duration in minutes [{duration}]: ").strip() or str(duration))
    cfg["automatic_updates"] = update
    cfg["automatic_reboot"] = reboot
    cfg["maintenance_window"] = {"enabled": enabled, "start": start, "duration_minutes": duration}
    if update and cfg.get("policy") == "check-only":
        policy = input("Kernel install policy [security-only/all-stable] (default all-stable): ").strip() or "all-stable"
        if policy not in {"security-only", "all-stable"}:
            raise core.LKSUError("Invalid install policy")
        cfg["policy"] = policy
    if reboot:
        if not cfg.get("services") and not cfg.get("health_urls"):
            detected = detect_active_host_services()
            choices = ", ".join(detected) if detected else "none"
            print("Detected running CyberPanel services: " + choices)
            names = input("Services to check before and after reboot (comma separated, Enter for detected): ").strip()
            parsed = [x.strip() for x in names.split(",") if x.strip()] if names else detected
            if any(not re.fullmatch(r"[A-Za-z0-9_.@-]+", x) for x in parsed):
                raise core.LKSUError("Invalid service name")
            cfg["services"] = parsed
            if parsed:
                print("Configured reboot health checks: " + ", ".join(parsed))
        validate_reboot_health_checks(cfg.get("services"), cfg.get("health_urls"))
        cfg["recovery_ready"] = yes_no(
            "Have you verified a current external snapshot AND provider console recovery?",
            cfg.get("recovery_ready", False),
        )
    else:
        cfg["recovery_ready"] = False
    from .policy import in_maintenance_window
    # Validate the schedule, but do not require it to be open now.
    if enabled:
        from datetime import datetime
        in_maintenance_window(cfg, datetime.now().astimezone())
    core.save(core.CONFIG, cfg)
    if enabled and (update or reboot):
        core.run("systemctl", "enable", "--now", "lksu-maintenance.timer")
    else:
        core.run("systemctl", "disable", "--now", "lksu-maintenance.timer")
    print("Kernel automation preferences and maintenance timer saved; SMTP settings preserved.")
    if (update or reboot) and not enabled:
        print("Warning: future automatic kernel installs and reboots are disabled without a maintenance window.")



def configure_self_update():
    """Explicit one-time opt-in for an existing configuration, without resetting SMTP."""
    if os.geteuid():
        raise core.LKSUError("Root required")
    cfg = core.config()
    answer = input("Automatically install verified LKSU application releases? [Y/n]: ").strip().lower()
    if answer not in {"", "y", "yes", "n", "no"}:
        raise core.LKSUError("Answer y or n")
    enabled = answer in {"", "y", "yes"}
    cfg["automatic_lksu_updates"] = enabled
    core.save(core.CONFIG, cfg)
    print("Automatic LKSU application updates: " + ("Enabled" if enabled else "Disabled"))


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


def main(argv=None):
    parser = argparse.ArgumentParser(description="AlmaLinux Kernel Security Updater")
    parser.add_argument("--json", action="store_true", help="Print the full machine-readable report instead of an operator summary")
    parser.add_argument("command", choices=("configure", "configure-automation", "configure-self-update", "initialize", "check", "scheduled", "apply", "maintenance", "stage-reboot", "verify", "select-old", "security-baseline", "security-check", "self-update", "self-update-check", "self-update-scheduled"))
    args = parser.parse_args(argv)
    reboot_requested = False
    mail_failure = None
    report_attempted = False
    cfg = None
    try:
        if args.command == "configure":
            setup()
            return 0
        if args.command == "configure-self-update":
            configure_self_update()
            return 0
        if args.command == "configure-automation":
            configure_automation()
            return 0
        cfg = core.config()
        if args.command == "initialize":
            with core.kernel_operation_lock():
                result, reboot_requested = core.initial_run(cfg)
        elif args.command == "self-update-check":
            result = self_update.check()
        elif args.command in {"self-update", "self-update-scheduled"}:
            result = self_update.update(automatic=args.command == "self-update-scheduled",
                                        enabled=cfg.get("automatic_lksu_updates", False))
        elif args.command == "security-baseline":
            if os.geteuid(): raise core.LKSUError("Root required")
            result = {"status": "baseline-created", "baseline": create_baseline(cfg)}
        elif args.command == "security-check":
            if os.geteuid(): raise core.LKSUError("Root required")
            result = security_check(cfg)
        elif args.command == "check":
            result = core.check()
        elif args.command == "apply":
            if os.geteuid():
                raise core.LKSUError("Root required")
            with core.kernel_operation_lock():
                result = core.apply(cfg["policy"])
        elif args.command == "scheduled":
            result = core.check()
        elif args.command == "maintenance":
            if not in_maintenance_window(cfg):
                # Collect a read-only assessment even when installation is deferred.
                result = {"status": "outside-maintenance-window", **core.check()}
            else:
                with core.kernel_operation_lock():
                    result, reboot_requested = core.maintenance(cfg)
        elif args.command == "stage-reboot":
            if not in_maintenance_window(cfg):
                raise core.LKSUError("Outside configured maintenance window")
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
                raise core.LKSUError("Root required")
            with core.kernel_operation_lock():
                result = {"old_default": core.select_old(), "rebooted": False}
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(format_console_report(cfg, args.command, result))
        routine_reports = args.command in {"initialize", "scheduled", "apply", "maintenance", "stage-reboot", "verify", "self-update", "self-update-scheduled"}
        report_attempted = True
        try:
            notifications.send_event(cfg, args.command, result, send_report, build_email_report)
        except (core.LKSUError, OSError, ValueError, KeyError, smtplib.SMTPException) as mail_error:
            mail_failure = mail_error
            print(f"LKSU event email delivery failed: {mail_error}", file=sys.stderr)
        if routine_reports or args.command == "security-check":
            send_fleet_report(cfg, {"command": args.command, "result": result, "hostname": os.uname().nodename, "reported_at": int(datetime.now().timestamp())})
        if reboot_requested:
            core.run("systemctl", "reboot")
        if mail_failure is not None:
            return 1
        return 0 if not (args.command == "verify" and not result["healthy"]) else 2
    except (core.LKSUError, OSError, ValueError, KeyError, smtplib.SMTPException) as exc:
        print(f"LKSU error: {exc}", file=sys.stderr)
        # Report failed scheduled actions too, without retrying a failed SMTP send.
        if cfg is not None and not report_attempted and args.command in notifications.UPDATE_COMMANDS:
            try:
                notifications.send_event(cfg, args.command, {"status": "error", "error": str(exc)},
                                         send_report, build_email_report)
            except (core.LKSUError, OSError, ValueError, KeyError, smtplib.SMTPException) as mail_error:
                print(f"LKSU report delivery failed: {mail_error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
