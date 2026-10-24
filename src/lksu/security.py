"""Low-impact host signals: detect and report, never remediate."""
import hashlib
import json
import os
import stat
import time
from pathlib import Path

from .core import CONFIG, LKSUError, run, save

SECURITY_STATE = Path("/var/lib/lksu/security-state.json")
BASELINE = Path("/var/lib/lksu/integrity.json")


def _digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def watched_paths(config):
    package_dir = Path(__file__).resolve().parent
    paths = {CONFIG, *package_dir.glob("*.py")}
    for raw in config.get("security_watch", {}).get("watched_files", []):
        paths.add(Path(raw))
    return sorted(paths, key=str)


def create_baseline(config):
    files = {}
    for path in watched_paths(config):
        if not path.exists() or path.is_symlink() or not path.is_file():
            raise LKSUError(f"Cannot baseline missing, linked or non-file path: {path}")
        info = path.stat()
        files[str(path)] = {"sha256": _digest(path), "uid": info.st_uid, "mode": stat.S_IMODE(info.st_mode)}
    value = {"created_at": int(time.time()), "files": files}
    save(BASELINE, value)
    return value


def _alert(code, severity, message, evidence=None):
    value = {"code": code, "severity": severity, "message": message}
    if evidence is not None:
        value["evidence"] = evidence
    return value


def _integrity_alerts(config):
    if not BASELINE.exists():
        return [_alert("baseline_missing", "high", "Integrity baseline is missing; run lksu security-baseline")]
    baseline = json.loads(BASELINE.read_text())
    alerts = []
    for raw, expected in baseline.get("files", {}).items():
        path = Path(raw)
        if not path.exists() or path.is_symlink() or not path.is_file():
            alerts.append(_alert("watched_file_missing", "high", f"Watched file missing or replaced: {path}")); continue
        info = path.stat(); actual = _digest(path)
        if actual != expected["sha256"]:
            alerts.append(_alert("watched_file_changed", "high", f"Watched file content changed: {path}", {"expected_sha256": expected["sha256"], "actual_sha256": actual}))
        if info.st_uid != expected["uid"] or stat.S_IMODE(info.st_mode) != expected["mode"]:
            alerts.append(_alert("watched_file_metadata", "medium", f"Watched file ownership or mode changed: {path}"))
    return alerts


def _platform_alerts(config):
    settings = config.get("security_watch", {})
    alerts = []
    for service in settings.get("required_services", ["auditd", "firewalld"]):
        if run("systemctl", "is-active", "--quiet", service, check=False).returncode:
            alerts.append(_alert("security_service_inactive", "high", f"Required security service is inactive: {service}"))
    if settings.get("require_selinux_enforcing", True):
        result = run("getenforce", check=False)
        if result.returncode or result.stdout.strip() != "Enforcing":
            alerts.append(_alert("selinux_not_enforcing", "high", "SELinux is not enforcing", result.stdout.strip() or result.stderr.strip()))
    return alerts


def _ssh_alerts(since, failed_threshold):
    result = run("journalctl", "--since", f"@{since}", "-u", "sshd", "-o", "json", "--no-pager", check=False)
    if result.returncode:
        return [_alert("sshd_journal_unavailable", "medium", "Could not read sshd journal")]
    failed = 0; roots = []
    for raw in result.stdout.splitlines():
        try: message = str(json.loads(raw).get("MESSAGE", ""))
        except json.JSONDecodeError: continue
        if "Failed password" in message or "authentication failure" in message: failed += 1
        if "Accepted " in message and " for root " in message: roots.append(message[:500])
    alerts = []
    if failed >= failed_threshold:
        alerts.append(_alert("ssh_failures", "medium", f"{failed} SSH authentication failures since the previous check", {"count": failed}))
    for message in roots:
        alerts.append(_alert("ssh_root_login", "high", "Successful SSH login as root", message))
    return alerts


def check(config, now=None):
    current = int(now or time.time())
    previous = current - 600
    if SECURITY_STATE.exists():
        try: previous = min(current, max(int(json.loads(SECURITY_STATE.read_text()).get("last_check", previous)), current - 86400))
        except (ValueError, json.JSONDecodeError): pass
    settings = config.get("security_watch", {})
    alerts = _integrity_alerts(config) + _platform_alerts(config) + _ssh_alerts(previous, int(settings.get("ssh_failure_threshold", 5)))
    save(SECURITY_STATE, {"last_check": current})
    severity_order = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    highest = max((severity_order.get(item["severity"], 0) for item in alerts), default=0)
    result = {"status": "alert" if alerts else "ok", "checked_at": current, "highest_severity": highest, "alerts": alerts, "automatic_changes": False}
    if alerts:
        result["recommended_action"] = "Review the evidence and host audit logs. Do not recreate the integrity baseline until every change is confirmed as trusted. LKSU made no automatic security change."
    return result
