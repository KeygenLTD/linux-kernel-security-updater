import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from lksu import policy

class PolicyTests(unittest.TestCase):
    def test_window_crosses_midnight(self):
        cfg = {"maintenance_window": {"start": "23:30", "duration_minutes": 120}}
        self.assertTrue(policy.in_maintenance_window(cfg, datetime(2026, 1, 2, 0, 15, tzinfo=timezone.utc)))
        self.assertFalse(policy.in_maintenance_window(cfg, datetime(2026, 1, 2, 2, 0, tzinfo=timezone.utc)))

    def test_explicit_no_window_allows_anytime_maintenance(self):
        cfg = {"maintenance_window": {"enabled": False, "start": "03:00", "duration_minutes": 60}}
        self.assertTrue(policy.in_maintenance_window(cfg, datetime(2026, 1, 2, 1, 0, tzinfo=timezone.utc)))
        self.assertTrue(policy.in_maintenance_window(cfg, datetime(2026, 1, 2, 17, 0, tzinfo=timezone.utc)))

    def test_missing_window_still_fails_closed(self):
        self.assertFalse(policy.in_maintenance_window({}))
        self.assertFalse(policy.in_maintenance_window({"maintenance_window": "bad"}))
        self.assertFalse(policy.in_maintenance_window({"maintenance_window": {}}))

    def test_advisory_extracts_cves(self):
        listing = type("P", (), {"returncode": 0, "stdout": "ALSA-2026:1234 Important/Sec. kernel-core-1.x86_64\n", "stderr": ""})()
        detail = type("P", (), {"returncode": 0, "stdout": "CVE-2026-12345 CVE-2026-12346", "stderr": ""})()
        with patch.object(policy, "run", side_effect=[listing, detail]):
            result = policy.security_advisories()
        self.assertEqual(result[0]["cves"], ["CVE-2026-12345", "CVE-2026-12346"])

if __name__ == "__main__": unittest.main()
