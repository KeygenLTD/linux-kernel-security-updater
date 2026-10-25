"""Regression checks for permanent 24/7 kernel monitoring and safe legacy upgrades."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lksu import cli, core


class ContinuousAutomationTests(unittest.TestCase):
    def test_existing_configuration_is_migrated_without_losing_credentials(self):
        old = {
            "email": "ops@example.com", "smtp_host": "smtp.example.com",
            "smtp_password": "secret", "smtp_port": 465,
            "automatic_updates": True, "automatic_reboot": True,
            "automatic_lksu_updates": True, "recovery_ready": True,
            "policy": "all-stable", "services": ["mariadb"],
            "health_urls": [], "notifications": True,
            "custom_extension": {"keep": [1, 2]},
            "maintenance_window": {"enabled": True, "start": "03:00", "duration_minutes": 60},
        }
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            target.write_text(json.dumps(old))
            target.chmod(0o600)
            with patch.object(core, "CONFIG", target):
                upgraded = core.config()
                persisted = json.loads(target.read_text())
                again = core.config()
            self.assertNotIn("maintenance_window", upgraded)
            self.assertEqual(upgraded, persisted)
            self.assertEqual(again, upgraded)
            self.assertEqual({k: v for k, v in old.items() if k != "maintenance_window"}, upgraded)
            self.assertEqual(os.stat(target).st_mode & 0o777, 0o600)

    def test_legacy_restricted_window_does_not_block_auto_kernel_install(self):
        cfg = {"maintenance_window": {"enabled": True, "start": "03:00", "duration_minutes": 60},
               "automatic_updates": True, "automatic_reboot": False, "policy": "all-stable"}
        with patch.object(core, "pending_update", return_value=None), patch.object(
            core, "apply", return_value={"status": "no-updates"}
        ) as apply:
            result, reboot = core.maintenance(cfg)
        apply.assert_called_once_with("all-stable")
        self.assertEqual(result["status"], "no-updates")
        self.assertFalse(reboot)

    def test_automatic_install_opt_out_remains_read_only(self):
        cfg = {"automatic_updates": False, "automatic_reboot": False, "policy": "check-only"}
        with patch.object(core, "pending_update", return_value=None), patch.object(
            core, "check", return_value={"status": "checked"}
        ) as check, patch.object(core, "apply") as apply:
            result, reboot = core.maintenance(cfg)
        self.assertFalse(reboot)
        self.assertEqual(result["status"], "checked")
        check.assert_called_once()
        apply.assert_not_called()

    def test_upgrade_keeps_auto_reboot_safety_gate(self):
        with self.assertRaisesRegex(core.LKSUError, "external snapshot"):
            core.auto_reboot_preflight({"automatic_reboot": True, "services": ["mariadb"]})


if __name__ == "__main__":
    unittest.main()
