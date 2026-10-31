"""Kernel security advisory classification."""
import re

from .core import LKSUError, run

ADVISORY = re.compile(r"^(?P<id>\S+)\s+(?P<severity>\S+)\s+(?P<package>kernel(?:-[a-z0-9-]+)?\S*)$", re.I)
CVE = re.compile(r"CVE-\d{4}-\d{4,}", re.I)


def security_advisories():
    result = run("dnf", "-q", "updateinfo", "list", "--security", "--available", "kernel*", check=False)
    if result.returncode not in (0, 100):
        raise LKSUError(f"DNF updateinfo failed: {result.stderr.strip()[:500]}")
    found = {}
    warning = None
    for raw in result.stdout.splitlines():
        match = ADVISORY.match(raw.strip())
        if not match:
            continue
        advisory_id = match.group("id")
        found.setdefault(advisory_id, {"id": advisory_id, "severity": match.group("severity"), "packages": [], "cves": []})
        found[advisory_id]["packages"].append(match.group("package"))
    if found:
        try:
            detail = run("dnf", "-q", "updateinfo", "info", "--security", "--available", "kernel*", check=False, timeout=20)
            if detail.returncode not in (0, 100):
                raise LKSUError("Could not read advisory details")
            blocks = re.split(r"(?=Update ID\s*:\s*)", detail.stdout, flags=re.I)
            for block in blocks:
                update_id = re.search(r"Update ID\s*:\s*(\S+)", block, re.I)
                if update_id and update_id.group(1) in found:
                    found[update_id.group(1)]["cves"] = sorted(set(x.upper() for x in CVE.findall(block)))
            # Never attribute an unscoped CVE to a kernel advisory: DNF output
            # may include unrelated package advisories or omit Update ID headers.
            if any(not item["cves"] for item in found.values()):
                warning = "Some kernel advisories have no verifiable CVE mapping in DNF metadata"
        except LKSUError as exc:
            warning = f"Advisory details unavailable: {exc}"
    result = sorted(found.values(), key=lambda item: item["id"])
    if warning:
        result.append({"warning": warning})
    return result

