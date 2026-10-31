import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lksu import cli, core


class InitialInstallTests(unittest.TestCase):
    def test_initial_install_runs_eligible_kernel_update_without_window_gate(self):
        cfg = {"automatic_updates": True, "automatic_reboot": False, "policy": "all-stable"}
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "initial-run.json"
            with patch.object(core, "INITIAL_STATE", marker), patch.object(core, "maintenance", return_value=(
                {"status": "installed-awaiting-manual-reboot", "running": "old"}, False
            )) as maintenance:
                result, reboot = core.initial_run(cfg)
                self.assertEqual(result["status"], "installed-awaiting-manual-reboot")
                self.assertFalse(reboot)
                maintenance.assert_called_once_with(cfg)
                self.assertTrue(json.loads(marker.read_text())["completed"])

    def test_reinstall_does_not_repeat_initial_install(self):
        cfg = {"automatic_updates": True, "automatic_reboot": True, "policy": "all-stable"}
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "initial-run.json"
            marker.write_text(json.dumps({"completed": True, "completed_at": 123}))
            with patch.object(core, "INITIAL_STATE", marker), patch.object(core, "maintenance") as maintenance:
                result, reboot = core.initial_run(cfg)
                self.assertEqual(result["status"], "initial-run-completed")
                self.assertFalse(reboot)
                maintenance.assert_not_called()

    def test_first_run_when_updates_not_authorized_only_checks(self):
        cfg = {"automatic_updates": False, "automatic_reboot": False, "policy": "check-only"}
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "initial-run.json"
            with patch.object(core, "INITIAL_STATE", marker), patch.object(
                core, "check", return_value={"running": "old", "updates": []}
            ) as check, patch.object(core, "maintenance") as maintenance:
                result, reboot = core.initial_run(cfg)
                self.assertEqual(result["status"], "initial-check-only")
                self.assertFalse(reboot)
                check.assert_called_once()
                maintenance.assert_not_called()

    def test_initial_install_failure_does_not_claim_completion(self):
        cfg = {"automatic_updates": True, "automatic_reboot": True, "policy": "all-stable"}
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "initial-run.json"
            with patch.object(core, "INITIAL_STATE", marker), patch.object(
                core, "maintenance", side_effect=core.LKSUError("recovery not verified")
            ):
                with self.assertRaisesRegex(core.LKSUError, "recovery not verified"):
                    core.initial_run(cfg)
                self.assertFalse(marker.exists())

    @patch("lksu.cli.core.kernel_operation_lock")
    @patch("lksu.cli.core.initial_run", return_value=(
        {"status": "no-updates", "running": "old", "updates": [], "security_advisories": []}, False
    ))
    @patch("lksu.cli.send_report")
    @patch("lksu.cli.send_fleet_report")
    @patch("lksu.cli.core.config", return_value={
        "automatic_updates": True, "automatic_reboot": False,
        "notifications": True, "policy": "all-stable",
    })
    def test_cli_initialize_has_real_command_and_reports(self, cfg, fleet, send, initial, lock):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(cli.main(["initialize"]), 0)
        initial.assert_called_once()
        self.assertIn("Package upgrades:", buffer.getvalue())
        send.assert_not_called()
        fleet.assert_called_once()

    @patch("lksu.cli.core.kernel_operation_lock")
    @patch("lksu.cli.core.initial_run", return_value=(
        {"status": "trial-boot-staged", "trial_boot": {"trial_entry": "x"}}, True
    ))
    @patch("lksu.cli.core.run")
    @patch("lksu.cli.send_report")
    @patch("lksu.cli.send_fleet_report")
    @patch("lksu.cli.core.config", return_value={
        "automatic_updates": True, "automatic_reboot": True,
        "notifications": False, "policy": "all-stable",
    })
    def test_cli_initial_setup_reboots_only_after_successful_staging(
        self, cfg, fleet, send, run, initial, lock
    ):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(cli.main(["initialize"]), 0)
        initial.assert_called_once()
        run.assert_called_once_with("systemctl", "reboot")
        self.assertIn("Requesting system reboot NOW", err.getvalue())
        self.assertIn("SSH may disconnect", err.getvalue())
        self.assertIn("Boot success is verified only after", err.getvalue())

    @patch("lksu.cli.core.kernel_operation_lock")
    @patch("lksu.cli.core.initial_run", return_value=(
        {"status": "trial-boot-staged", "trial_boot": {"trial_entry": "x"},
         "new_default": "/boot/vmlinuz-5.14.0-687.59.1.el9_8.x86_64"}, True
    ))
    @patch("lksu.cli.core.run")
    @patch("lksu.cli.send_fleet_report")
    @patch("lksu.cli.core.config", return_value={
        "automatic_updates": True, "automatic_reboot": True, "notifications": False
    })
    def test_reboot_status_keeps_machine_readable_stdout_clean(self, cfg, fleet, run, initial, lock):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(cli.main(["--json", "initialize"]), 0)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "trial-boot-staged")
        self.assertIn("Requesting system reboot NOW", stderr.getvalue())
        self.assertNotIn("LKSU [REBOOT]", stdout.getvalue())
        run.assert_called_once_with("systemctl", "reboot")

    @patch("lksu.cli.core.kernel_operation_lock")
    @patch("lksu.cli.core.initial_run", return_value=(
        {"status": "trial-boot-staged", "trial_boot": {"trial_entry": "x"}}, True
    ))
    @patch("lksu.cli.core.run", side_effect=core.LKSUError("systemctl reboot refused"))
    @patch("lksu.cli.send_fleet_report")
    @patch("lksu.cli.core.config", return_value={
        "automatic_updates": True, "automatic_reboot": True, "notifications": False
    })
    def test_failed_reboot_request_is_visible(self, cfg, fleet, run, initial, lock):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("lksu.progress._language", return_value="en"), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(cli.main(["initialize"]), 1)
        self.assertIn("Requesting system reboot NOW", stderr.getvalue())
        self.assertIn("Reboot request failed", stderr.getvalue())
        run.assert_called_once_with("systemctl", "reboot")


if __name__ == "__main__":
    unittest.main()
