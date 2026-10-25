import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from lksu import core, notifications


CFG = {"notifications": True}
CHECK = {"running": "old", "updates": [], "status": "outside-maintenance-window"}


class EventEmailTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "notifications.json"
        self.patched = patch.object(notifications, "NOTIFICATION_STATE", self.state)
        self.patched.start()
        self.addCleanup(self.patched.stop)
        self.send = Mock()
        self.format = Mock(return_value=("English title", "English report"))

    def notify(self, command, result):
        return notifications.send_event(CFG, command, result, self.send, self.format)

    def test_successful_checks_never_mail(self):
        for command in ("check", "scheduled", "maintenance", "self-update-check", "security-check"):
            self.assertFalse(self.notify(command, CHECK))
        self.assertFalse(self.notify("maintenance", {"status": "no-updates", "updates": []}))
        self.assertFalse(self.notify("maintenance", {"status": "no-security-updates"}))
        self.assertFalse(self.notify("verify", {"status": "no-pending-verification", "healthy": True, "verification_performed": False}))
        self.assertFalse(self.notify("self-update-scheduled", {"status": "self-update-current"}))
        self.send.assert_not_called()
        self.format.assert_not_called()

    def test_installed_kernel_emails_once_even_after_another_check(self):
        result = {"status": "installed-awaiting-manual-reboot", "old_kernel": "old", "new_default": "/boot/vmlinuz-new"}
        self.assertTrue(self.notify("maintenance", result))
        self.assertFalse(self.notify("maintenance", result))
        self.assertFalse(self.notify("scheduled", CHECK))
        self.assertEqual(self.send.call_count, 1)
        self.assertTrue(self.state.exists())

    def test_blocked_reboot_sends_one_actionable_failure(self):
        result = {"status": "reboot-blocked", "reboot_block_reason": "No provider snapshot", "new_default": "/boot/vmlinuz-new"}
        self.assertTrue(self.notify("maintenance", result))
        self.assertFalse(self.notify("maintenance", result))
        self.assertEqual(self.send.call_count, 1)

    def test_error_deduplicates_and_alerts_on_distinct_failure(self):
        self.assertTrue(self.notify("maintenance", {"status": "error", "error": "DNF timeout"}))
        self.assertFalse(self.notify("maintenance", {"status": "error", "error": "DNF timeout"}))
        self.assertTrue(self.notify("maintenance", {"status": "error", "error": "GRUB unavailable"}))
        self.assertEqual(self.send.call_count, 2)

    def test_post_boot_verification_mail_once_on_success(self):
        result = {"healthy": True, "running": "new", "old_kernel": "old", "services": {"service:lsws": True}}
        self.assertTrue(self.notify("verify", result))
        self.assertFalse(self.notify("verify", result))
        self.assertEqual(self.send.call_count, 1)

    def test_failed_postboot_checks_alert_once(self):
        result = {"healthy": False, "running": "new", "services": {"service:lsws": False}}
        self.assertTrue(self.notify("verify", result))
        self.assertFalse(self.notify("verify", result))
        self.assertEqual(self.send.call_count, 1)

    def test_self_updates_only_mail_on_actual_new_release(self):
        self.assertFalse(self.notify("self-update-scheduled", {"status": "self-update-current", "installed_version": "v0.3.13"}))
        self.assertTrue(self.notify("self-update-scheduled", {"status": "self-updated", "installed_version": "v0.3.14"}))
        self.assertFalse(self.notify("self-update-scheduled", {"status": "self-updated", "installed_version": "v0.3.14"}))
        self.assertEqual(self.send.call_count, 1)

    def test_mail_failure_does_not_mark_event_delivered(self):
        self.send.side_effect = OSError("SMTP unavailable")
        r = {"status": "error", "error": "DNF failed"}
        with self.assertRaises(OSError):
            self.notify("maintenance", r)
        self.assertFalse(self.state.exists())
        self.send.side_effect = None
        self.assertTrue(self.notify("maintenance", r))
        self.assertEqual(self.send.call_count, 2)

    def test_notifications_can_be_disabled(self):
        self.assertFalse(notifications.send_event(
            {"notifications": False}, "maintenance", {"status": "error", "error": "failed"}, self.send, self.format
        ))
        self.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
