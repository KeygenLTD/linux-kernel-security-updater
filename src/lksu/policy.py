"""Advisory classification and maintenance-window decisions."""
from datetime import datetime, time, timedelta
import re

from .core import LKSUError, run

ADVISORY = re.compile(r"^(?P<id>\S+)\s+(?P<severity>\S+)\s+(?P<package>kernel(?:-[a-z0-9-]+)?\S*)$", re.I)
CVE = re.compile(r"CVE-\d{4}-\d{4,}", re.I)


def security_advisories():
    result = run("dnf", "-q", "updateinfo", "list", "--security", "--available", "kernel*", check=False)
    if result.returncode not in (0, 100):
        raise LKSUError(f"DNF updateinfo failed: {result.stderr.strip()[:500]}")
    found = {}
    for raw in result.stdout.splitlines():
        match = ADVISORY.match(raw.strip())
        if not match:
            continue
        advisory_id = match.group("id")
        detail = run("dnf", "-q", "updateinfo", "info", advisory_id, check=False)
        if detail.returncode:
            raise LKSUError(f"Could not read advisory {advisory_id}")
        cves = sorted(set(x.upper() for x in CVE.findall(detail.stdout)))
        found.setdefault(advisory_id, {"id": advisory_id, "severity": match.group("severity"), "packages": [], "cves": cves})
        found[advisory_id]["packages"].append(match.group("package"))
    return sorted(found.values(), key=lambda item: item["id"])


def in_maintenance_window(config, now=None):
    window = config.get("maintenance_window")
    if not window:
        return False
    try:
        hour, minute = map(int, window["start"].split(":"))
        duration = int(window.get("duration_minutes", 60))
    except (KeyError, TypeError, ValueError):
        raise LKSUError("Invalid maintenance_window configuration")
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 1 <= duration <= 720):
        raise LKSUError("Maintenance window is outside allowed bounds")
    current = now or datetime.now().astimezone()
    start = datetime.combine(current.date(), time(hour, minute), tzinfo=current.tzinfo)
    if current < start:
        start -= timedelta(days=1)
    return start <= current < start + timedelta(minutes=duration)
