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
        self.assertIn("recovery boot", body)


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
        result = report.call_args.args[2]
        self.assertEqual(result["status"], "outside-maintenance-window")
        self.assertEqual(len(result["updates"]), 1)
        send.assert_called_once_with(CONFIG, "English subject", "English body")
        fleet.assert_called_once()

    @patch("lksu.cli.send_fleet_report")
    @patch("lksu.cli.send_report", side_effect=smtplib.SMTPException("mail failed"))
    @patch("lksu.cli.build_email_report", return_value=("subject", "body"))
    @patch("lksu.cli.core.check", return_value={"running": "old", "updates": []})
    @patch("lksu.cli.core.config", return_value=CONFIG)
    def test_failed_smtp_does_not_trigger_second_send(self, _cfg, _check, _report, send, _fleet):
        self.assertEqual(cli.main(["scheduled"]), 1)
        self.assertEqual(send.call_count, 1)

    @patch("lksu.cli.send_report")
    @patch("lksu.cli.build_email_report", return_value=("error subject", "error body"))
    @patch("lksu.cli.core.check", side_effect=cli.core.LKSUError("DNF unavailable"))
    @patch("lksu.cli.core.config", return_value=CONFIG)
    def test_scheduled_failure_sends_english_error_report(self, _cfg, _check, report, send):
        self.assertEqual(cli.main(["scheduled"]), 1)
        self.assertEqual(report.call_args.args[2]["status"], "error")
        send.assert_called_once_with(CONFIG, "error subject", "error body")


if __name__ == "__main__":
    unittest.main()
