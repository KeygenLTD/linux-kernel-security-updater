import smtplib
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from lksu import cli
from lksu.reporting import build_email_report


WHEN = datetime(2026, 10, 25, 2, 0, tzinfo=timezone.utc)
CONFIG = {
    "policy": "security-only",
    "notifications": True,
    "automatic_updates": True,
    "automatic_reboot": False,
    "maintenance_window": {"enabled": True, "start": "03:00", "duration_minutes": 60},
}


def render(command, result):
    with patch("lksu.reporting.core.STATE") as state:
        state.exists.return_value = False
        return build_email_report(
            CONFIG, command, result, timestamp=WHEN, hostname="test-node",
            os_name="AlmaLinux 10", installed_kernels=["6.12.0-previous"],
        )


class ReportTests(unittest.TestCase):
    def test_outside_window_reports_real_available_updates(self):
        subject, body = render("maintenance", {
            "status": "outside-maintenance-window",
            "running": "6.12.0-current",
            "updates": [{"name": "kernel-core", "evr": "6.12.0-new", "arch": "x86_64"}],
            "security_advisories": [{"id": "ALSA-2026:1234", "severity": "Important", "cves": ["CVE-2026-12345"]}],
        })
        self.assertEqual(subject, "LKSU [DEFERRED] test-node | maintenance")
        self.assertIn("Kernel package upgrades: 1", body)
        self.assertIn("Security advisories: 1", body)
        self.assertIn("installation skipped outside the maintenance window", body)
        self.assertIn("Rollback kernel:", body)
        self.assertIn("Next scheduled check: Not determined", body)
        self.assertNotIn('{"status":', body)

    def test_unknown_update_information_is_not_zero(self):
        subject, body = render("maintenance", {"status": "outside-maintenance-window", "running": "6.12.0-current"})
        self.assertIn("[SKIPPED]", subject)
        self.assertIn("Kernel package upgrades: Not checked", body)
        self.assertNotIn("No kernel package upgrades found", body)

    def test_error_report_requires_action(self):
        subject, body = render("scheduled", {"status": "error", "error": "DNF metadata request failed", "running": "6.12.0-current"})
        self.assertIn("[ERROR]", subject)
        self.assertIn("Action required: Yes", body)
        self.assertIn("DNF metadata request failed", body)
        self.assertIn("Kernel package upgrades: Not checked", body)

    def test_completed_check_not_reported_as_installed(self):
        subject, body = render("scheduled", {"running": "6.12.0-current", "updates": [], "security_advisories": []})
        self.assertIn("[NO UPDATES]", subject)
        self.assertIn("Automatic installation: Enabled", body)
        self.assertNotIn("Kernel packages installed", body)

    def test_rollback_not_assumed_verified(self):
        _, body = render("apply", {"status": "installed-awaiting-manual-reboot", "old_kernel": "6.12.0-previous"})
        self.assertIn("rollback availability NOT verified", body)
        self.assertIn("Confirm provider-console recovery", body)


class MaintenancePolicyTests(unittest.TestCase):
    def test_explicit_no_window_permits_automatic_installation(self):
        from lksu.policy import in_maintenance_window
        anytime = {"maintenance_window": {"enabled": False, "start": "02:00", "duration_minutes": 60}}
        now = datetime(2026, 10, 25, 22, 30, tzinfo=timezone.utc)
        self.assertTrue(in_maintenance_window(anytime, now=now))

    def test_missing_window_does_not_authorize_automatic_installation(self):
        from lksu.policy import in_maintenance_window
        self.assertFalse(in_maintenance_window({}, now=datetime(2026, 10, 25, tzinfo=timezone.utc)))


class CLIReportTests(unittest.TestCase):
    @patch("lksu.cli.send_fleet_report")
    @patch("lksu.cli.send_report")
    @patch("lksu.cli.build_email_report", return_value=("English subject", "English body"))
    @patch("lksu.cli.core.apply")
    @patch("lksu.cli.core.check", return_value={"running": "old", "updates": [{"name": "kernel-core"}]})
    @patch("lksu.cli.in_maintenance_window", return_value=False)
    @patch("lksu.cli.core.config", return_value=CONFIG)
    def test_maintenance_outside_window_checks_without_updating(
        self, _config, _window, check, apply, report, send, fleet
    ):
        self.assertEqual(cli.main(["maintenance"]), 0)
        check.assert_called_once_with()
        apply.assert_not_called()
        report.assert_not_called()
        send.assert_not_called()
        fleet.assert_called_once()

    @patch("lksu.cli.send_fleet_report")
    @patch("lksu.cli.send_report", side_effect=smtplib.SMTPException("mail failed"))
    @patch("lksu.cli.build_email_report", return_value=("subject", "body"))
    @patch("lksu.cli.core.apply", return_value={
        "status": "installed-awaiting-manual-reboot",
        "old_kernel": "old", "new_default": "/boot/vmlinuz-new"
    })
    @patch("lksu.cli.core.config", return_value=CONFIG)
    @patch("lksu.cli.core.kernel_operation_lock")
    @patch("lksu.notifications.NOTIFICATION_STATE")
    def test_failed_smtp_does_not_trigger_second_send(
        self, state, lock, _cfg, _apply, _report, send, _fleet
    ):
        state.exists.return_value = False
        self.assertEqual(cli.main(["apply"]), 1)
        self.assertEqual(send.call_count, 1)

    @patch("lksu.notifications.core.save")
    @patch("lksu.cli.send_report")
    @patch("lksu.cli.build_email_report", return_value=("error subject", "error body"))
    @patch("lksu.cli.core.apply", side_effect=cli.core.LKSUError("DNF unavailable"))
    @patch("lksu.cli.core.config", return_value=CONFIG)
    @patch("lksu.cli.core.kernel_operation_lock")
    @patch("lksu.notifications.NOTIFICATION_STATE")
    def test_failed_update_sends_english_error_report(
        self, state, lock, _cfg, _apply, report, send, _save
    ):
        state.exists.return_value = False
        self.assertEqual(cli.main(["apply"]), 1)
        self.assertEqual(report.call_args.args[2]["status"], "error")
        send.assert_called_once_with(CONFIG, "error subject", "error body")

    @patch("lksu.cli.send_report")
    @patch("lksu.cli.build_email_report")
    @patch("lksu.cli.core.check", side_effect=cli.core.LKSUError("DNF unavailable"))
    @patch("lksu.cli.core.config", return_value=CONFIG)
    def test_scheduled_check_failure_does_not_email(self, _cfg, _check, report, send):
        self.assertEqual(cli.main(["scheduled"]), 1)
        report.assert_not_called()
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
