import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from lksu import debian_backend


class GrubPromotionSafetyTests(unittest.TestCase):
    def test_failed_persistent_default_does_not_complete_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = pathlib.Path(tmp) / "state.json"
            state_path.write_text(json.dumps({
                "backend": "debian-apt-grub", "pending": True,
                "new_default": "/boot/vmlinuz-6.1-new",
                "old_kernel": "6.1-old", "trial_entry": "advanced>new"}))
            with patch.object(debian_backend.subprocess, "run", side_effect=[
                subprocess.CompletedProcess([], 0),
                subprocess.CompletedProcess([], 0, stdout="saved_entry=advanced>old\n"),
            ]):
                with self.assertRaises(debian_backend.DebianKernelError):
                    debian_backend.verify_managed(state_path, "6.1-new", True)
            saved = json.loads(state_path.read_text())
            self.assertTrue(saved["pending"])
            self.assertNotIn("last_known_good", saved)

    def test_no_trial_entry_cannot_promote(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = pathlib.Path(tmp) / "state.json"
            state_path.write_text(json.dumps({
                "backend": "debian-apt-grub", "pending": True,
                "new_default": "/boot/vmlinuz-6.1-new",
                "old_kernel": "6.1-old", "trial_entry": None}))
            with patch.object(debian_backend.subprocess, "run") as run:
                with self.assertRaises(debian_backend.DebianKernelError):
                    debian_backend.verify_managed(state_path, "6.1-new", True)
                run.assert_not_called()
            self.assertTrue(json.loads(state_path.read_text())["pending"])


if __name__ == "__main__":
    unittest.main()
