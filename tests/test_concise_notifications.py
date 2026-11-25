"""Regression tests for operator-focused notification behavior."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from lksu.notifications import classify
from lksu.reporting import build_email_report


class ConciseNotificationTests(unittest.TestCase):
    def test_staging_is_silent(self):
        self.assertIsNone(classify("maintenance", {"status": "trial-boot-staged"}))
        self.assertIsNone(classify("stage-reboot", {"status": "trial-boot-staged", "trial_entry": "test"}))

    def test_verified_is_not_silent(self):
        self.assertEqual(classify("verify", {"healthy": True, "running": "6.1"})[0], "kernel-verified")

    def test_failed_verification_is_actionable(self):
        self.assertEqual(classify("verify", {"healthy": False, "running": "6.1"})[0], "failed:verification")

    def test_manual_reboot_remains_actionable(self):
        self.assertEqual(classify("maintenance", {"status": "installed-awaiting-manual-reboot"})[0], "action:manual-reboot")

    def test_turkish_verified_report(self):
        with patch("lksu.reporting.socket.gethostname", return_value="host"):
            subject, body = build_email_report(
                {"report_language": "tr", "display_name": "Sunucum"},
                "verify", {"healthy": True, "running": "6.1", "old_kernel": "6.0"},
                timestamp=datetime(2026, 11, 3, tzinfo=timezone.utc))
        self.assertIn("Güncelleme Başarılı", subject)
        self.assertIn("Sunucum", subject)
        self.assertIn("İşlem gerekmiyor", body)
        self.assertNotIn("TRIAL BOOT STAGED", body)


if __name__ == "__main__":
    unittest.main()
