import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from lksu import security


class SecurityTests(unittest.TestCase):
    def test_changed_file_creates_high_alert_without_remediation(self):
        with tempfile.TemporaryDirectory(dir=".") as temp:
            root = Path(temp); watched = root / "watched.conf"; watched.write_text("safe")
            baseline = root / "baseline.json"; state = root / "state.json"
            cfg = {"security_watch": {"watched_files": [str(watched)], "required_services": [], "require_selinux_enforcing": False}}
            with patch.object(security, "BASELINE", baseline), patch.object(security, "SECURITY_STATE", state), patch.object(
                security, "watched_paths", return_value=[watched]
            ), patch.object(security, "_ssh_alerts", return_value=[]):
                security.create_baseline(cfg); watched.write_text("changed")
                result = security.check(cfg, now=1000)
            self.assertEqual(result["status"], "alert")
            self.assertFalse(result["automatic_changes"])
            self.assertEqual(result["alerts"][0]["code"], "watched_file_changed")

    def test_missing_baseline_is_reported(self):
        with tempfile.TemporaryDirectory(dir=".") as temp:
            with patch.object(security, "BASELINE", Path(temp) / "missing.json"), patch.object(
                security, "SECURITY_STATE", Path(temp) / "state.json"
            ), patch.object(security, "_platform_alerts", return_value=[]), patch.object(security, "_ssh_alerts", return_value=[]):
                result = security.check({}, now=1000)
        self.assertEqual(result["alerts"][0]["code"], "baseline_missing")


if __name__ == "__main__": unittest.main()
