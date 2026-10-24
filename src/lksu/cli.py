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
from .security import check as security_check, create_baseline


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
    def yes_no(prompt, default):
        suffix = "Y/n" if default else "y/N"
        value = input(f"{prompt} [{suffix}]: ").strip().lower()
        if not value:
            return default
        if value not in {"y", "yes", "n", "no"}:
            raise core.LKSUError("Answer y or n")
        return value in {"y", "yes"}

    automatic_updates = yes_no("Enable automatic kernel updates?", False)
    notifications = yes_no("Send an email after every check/update?", True)
    automatic_reboot = yes_no("Enable automatic reboot?", False)
    use_window = yes_no("Use a maintenance window?", False)
    start = input("Maintenance start [03:00]: ").strip() or "03:00" if use_window else "03:00"
    duration = int(input("Maintenance duration in minutes [60]: ").strip() or "60") if use_window else 60
    policy = input("Install policy [check-only/security-only/all-stable] (default check-only): ").strip() or "check-only"
    if automatic_updates and policy == "check-only":
        policy = "security-only"
    if policy not in {"check-only", "security-only", "all-stable"}:
        raise core.LKSUError("Invalid install policy")
    services = input("Services to verify after reboot (comma separated, optional): ").strip()
    parsed = [x.strip() for x in services.split(",") if x.strip()]
    if any(not re.fullmatch(r"[A-Za-z0-9_.@-]+", x) for x in parsed):
        raise core.LKSUError("Invalid service name")
    health_urls = input("HTTP/HTTPS health URLs (comma separated, optional): ").strip()
    parsed_urls = [{"url": x.strip(), "status": 200} for x in health_urls.split(",") if x.strip()]
    core.save(core.CONFIG, {"email": email, "smtp_host": host, "smtp_port": port,
                            "smtp_user": user, "smtp_password": password, "policy": policy,
                            "services": parsed, "health_urls": parsed_urls,
                            "automatic_updates": automatic_updates, "notifications": notifications,
                            "automatic_reboot": automatic_reboot,
                            "maintenance_window": {"enabled": use_window, "start": start, "duration_minutes": duration},
                            "security_watch": {"required_services": ["auditd", "firewalld"],
                                               "require_selinux_enforcing": True,
                                               "ssh_failure_threshold": 5,
                                               "watched_files": ["/etc/ssh/sshd_config", "/etc/sudoers"]}})
    print(f"Configuration saved; automatic reboot is {'enabled' if automatic_reboot else 'disabled'}.")


def send_report(cfg, subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["smtp_user"]
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
    parser.add_argument("command", choices=("configure", "check", "scheduled", "apply", "maintenance", "stage-reboot", "verify", "select-old", "security-baseline", "security-check"))
    args = parser.parse_args(argv)
    reboot_requested = False
    try:
        if args.command == "configure":
            setup()
            return 0
        cfg = core.config()
        if args.command == "security-baseline":
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
            result = core.apply(cfg["policy"])
        elif args.command == "scheduled":
            result = core.check()
        elif args.command == "maintenance":
            if not in_maintenance_window(cfg):
                result = {"status": "outside-maintenance-window"}
            else:
                result = core.apply(cfg["policy"]) if cfg.get("automatic_updates") and cfg["policy"] != "check-only" else core.check()
                if cfg.get("automatic_reboot") and result.get("status") == "installed-awaiting-manual-reboot":
                    result["trial_boot"] = core.stage_trial_boot()
                    reboot_requested = True
        elif args.command == "stage-reboot":
            if not in_maintenance_window(cfg):
                raise core.LKSUError("Outside configured maintenance window")
            result = core.stage_trial_boot()
            if cfg.get("automatic_reboot"):
                reboot_requested = True
        elif args.command == "verify":
            result = core.verify(cfg)
        else:
            if os.geteuid():
                raise core.LKSUError("Root required")
            result = {"old_default": core.select_old(), "rebooted": False}
        output = json.dumps(result, indent=2)
        print(output)
        routine_reports = args.command in {"scheduled", "apply", "maintenance", "stage-reboot", "verify"}
        if (routine_reports and cfg.get("notifications", True)) or (args.command == "security-check" and result["alerts"]):
            send_report(cfg, f"LKSU {args.command} {datetime.now().isoformat(timespec='minutes')}", output)
        if routine_reports or args.command == "security-check":
            send_fleet_report(cfg, {"command": args.command, "result": result, "hostname": os.uname().nodename, "reported_at": int(datetime.now().timestamp())})
        if reboot_requested:
            core.run("systemctl", "reboot")
        return 0 if not (args.command == "verify" and not result["healthy"]) else 2
    except (core.LKSUError, OSError, ValueError, KeyError, smtplib.SMTPException) as exc:
        print(f"LKSU error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
