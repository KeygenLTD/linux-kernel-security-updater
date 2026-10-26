import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from lksu import debian_backend as backend


class ManagedTrialFailureTests(unittest.TestCase):
    def test_failed_grub_selection_keeps_transaction_retriable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "state.json"
            path.write_text(json.dumps({
                "backend": "debian-apt-grub", "pending": True,
                "new_default": "/boot/vmlinuz-6.1-new",
                "old_kernel": "6.1-old", "trial_entry": None}))
            with patch.object(backend, "boot_images", return_value={
                "6.1-new": object(), "6.1-old": object()}), \
                 patch.object(backend, "grub_menu_entry", side_effect=lambda release: "advanced>new" if release == "6.1-new" else "advanced>old"), \
                 patch.object(backend.subprocess, "run", return_value=type("R", (), {"returncode": 0, "stdout": "saved_entry=advanced>old\n"})()), \
                 patch.object(backend, "stage_one_shot",
                              side_effect=backend.DebianKernelError("GRUB failed")):
                with self.assertRaises(backend.DebianKernelError):
                    backend.stage_managed_trial(path)
            self.assertIsNone(json.loads(path.read_text())["trial_entry"])

    def test_successful_trial_records_grub_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "state.json"
            path.write_text(json.dumps({
                "backend": "debian-apt-grub", "pending": True,
                "new_default": "/boot/vmlinuz-6.1-new",
                "old_kernel": "6.1-old", "trial_entry": None}))
            with patch.object(backend, "boot_images", return_value={
                "6.1-new": object(), "6.1-old": object()}), \
                 patch.object(backend, "grub_menu_entry", side_effect=lambda release: "advanced>new" if release == "6.1-new" else "advanced>old"), \
                 patch.object(backend.subprocess, "run", return_value=type("R", (), {"returncode": 0, "stdout": "saved_entry=advanced>old\\n"})()), \
                 patch.object(backend, "stage_one_shot",
                              return_value={"candidate": "6.1-new", "rebooted": False}):
                backend.stage_managed_trial(path)
            self.assertEqual(json.loads(path.read_text())["trial_entry"], "advanced>new")


if __name__ == "__main__":
    unittest.main()
