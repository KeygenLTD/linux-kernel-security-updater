import unittest
from pathlib import Path
from unittest.mock import patch

from lksu import policy


class PolicyTests(unittest.TestCase):
    def test_kernel_timer_checks_every_fifteen_minutes_at_all_hours(self):
        timer = Path("systemd/lksu-maintenance.timer").read_text()
        self.assertIn("OnCalendar=*:0/15", timer)
        self.assertIn("Persistent=true", timer)
        self.assertNotIn("03:00", timer)

    def test_advisory_extracts_cves(self):
        listing = type("P", (), {"returncode": 0, "stdout": "ALSA-2026:1234 Important/Sec. kernel-core-1.x86_64\n", "stderr": ""})()
        detail = type("P", (), {"returncode": 0, "stdout": "CVE-2026-12345 CVE-2026-12346", "stderr": ""})()
        with patch.object(policy, "run", side_effect=[listing, detail]):
            result = policy.security_advisories()
        self.assertEqual(result[0]["cves"], ["CVE-2026-12345", "CVE-2026-12346"])


if __name__ == "__main__":
    unittest.main()
