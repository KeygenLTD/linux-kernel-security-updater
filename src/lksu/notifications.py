"""Event-only email notifications with durable deduplication.

Periodic checks never send emails. Only actual update transitions or attempted
update failures emit an event. A failed SMTP delivery does not mark it sent.
"""
import hashlib
import json
from pathlib import Path

from . import core

NOTIFICATION_STATE = Path("/var/lib/lksu/notifications.json")
UPDATE_COMMANDS = {
    "initialize", "apply", "maintenance", "stage-reboot", "verify",
    "self-update", "self-update-scheduled",
}


def classify(command, result):
    if command not in UPDATE_COMMANDS:
        return None
    status = result.get("status")
    if status == "error":
        return "failed:" + command, [result.get("error", "unknown error")]
    if status == "reboot-blocked":
        return "failed:reboot", [
            result.get("reboot_block_reason", "Unknown recovery failure"),
            result.get("new_default") or result.get("reboot_target"),
        ]
    if status == "self-updated":
        return "lksu-updated", [result.get("installed_version")]
    if status == "installed-awaiting-manual-reboot":
        return "kernel-installed", [result.get("old_kernel"), result.get("new_default")]
    if status == "trial-boot-staged" or (command == "stage-reboot" and result.get("trial_entry")):
        trial = result.get("trial_boot") or result
        return "kernel-trial-staged", [
            trial.get("trial_entry"), result.get("new_default"), result.get("old_kernel")
        ]
    if command == "verify" and result.get("verification_performed") is not False and "healthy" in result:
        if result["healthy"]:
            return "kernel-verified", [result.get("running"), result.get("old_kernel")]
        return "failed:verification", [
            result.get("running"), result.get("old_kernel"),
            result.get("services", {}), result.get("recommended_action"),
        ]
    return None


def _load():
    if not NOTIFICATION_STATE.exists():
        return {}
    try:
        state = json.loads(NOTIFICATION_STATE.read_text())
    except (OSError, ValueError) as exc:
        raise core.LKSUError("Notification state is unreadable; refusing to send duplicate mail") from exc
    if not isinstance(state, dict):
        raise core.LKSUError("Invalid notification state")
    return state


def send_event(cfg, command, result, send_mail, build_report):
    """Send once per distinct event; return True only for an email actually sent."""
    if not cfg.get("notifications", True):
        return False
    match = classify(command, result)
    if match is None:
        return False
    category, facts = match
    digest = hashlib.sha256(json.dumps([category, facts], sort_keys=True, default=str).encode()).hexdigest()
    state = _load()
    if state.get(category) == digest:
        return False
    subject, body = build_report(cfg, command, result)
    send_mail(cfg, subject, body)
    state[category] = digest
    # Clear a previous operation error only when a real successful update occurs.
    if not category.startswith("failed:"):
        state.pop("failed:" + command, None)
    core.save(NOTIFICATION_STATE, state)
    return True
