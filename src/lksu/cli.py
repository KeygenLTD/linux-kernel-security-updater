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


def setup():
    if os.geteuid():
        raise core.LKSUError("Root required")
    core.os_version()
    email = input("Report email: ").strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise core.LKSUError("Invalid email address")
    host = input("SMTP host: ").strip()
    if not re.fullmatch(r"[A-Za-z0-9.-]+", host):
        raise core.LKSUError("Invalid SMTP host")
    port = int(input("SMTP port [465]: ").strip() or "465")
    if port < 1 or port > 65535:
        raise core.LKSUError("Invalid port")
    user = input("SMTP username: ").strip()
    password = getpass.getpass("SMTP password or app password: ")
    if not user or not password:
        raise core.LKSUError("SMTP authentication is required")
    policy = input("Install policy [check-only/security-only/all-stable] (default check-only): ").strip() or "check-only"
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
                            "services": parsed, "health_urls": parsed_urls, "automatic_reboot": False,
                            "maintenance_window": {"start": "03:00", "duration_minutes": 60}})
    print("Configuration saved; automatic reboot is disabled.")


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
    parser.add_argument("command", choices=("configure", "check", "scheduled", "apply", "maintenance", "stage-reboot", "verify", "select-old"))
    args = parser.parse_args(argv)
    reboot_requested = False
    try:
        if args.command == "configure":
            setup()
            return 0
        cfg = core.config()
        if args.command == "check":
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
                result = core.apply(cfg["policy"]) if cfg["policy"] != "check-only" else core.check()
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
        if args.command in {"scheduled", "apply", "maintenance", "stage-reboot", "verify"}:
            send_report(cfg, f"LKSU {args.command} {datetime.now().isoformat(timespec='minutes')}", output)
            send_fleet_report(cfg, {"command": args.command, "result": result, "hostname": os.uname().nodename, "reported_at": int(datetime.now().timestamp())})
        if reboot_requested:
            core.run("systemctl", "reboot")
        return 0 if not (args.command == "verify" and not result["healthy"]) else 2
    except (core.LKSUError, OSError, ValueError, KeyError, smtplib.SMTPException) as exc:
        print(f"LKSU error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
