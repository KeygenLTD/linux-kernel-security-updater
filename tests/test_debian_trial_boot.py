import pathlib
import tempfile
import unittest
from unittest.mock import patch
from lksu import debian_backend as backend


class DebianTrialBootTests(unittest.TestCase):
    def test_nested_grub_entry_and_one_shot(self):
        cfg = """submenu 'Advanced options' $menuentry_id_option 'advanced-abc' {
 menuentry 'Linux new' --id 'linux-new' {
  linux /boot/vmlinuz-6.1.0-new root=/dev/vda ro
 }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "grub.cfg"
            path.write_text(cfg)
            self.assertEqual(backend.grub_menu_entry("6.1.0-new", path),
                             "advanced-abc>linux-new")
            calls = []
            class Result:
                returncode = 0
            def runner(args, **kwargs):
                calls.append(args)
                return Result()
            with patch.object(backend, "boot_images", return_value={"6.1.0-new": object()}):
                result = backend.stage_one_shot("6.1.0-new", runner=runner, config=path)
            self.assertEqual(calls, [["grub-reboot", "advanced-abc>linux-new"]])
            self.assertFalse(result["rebooted"])

    def test_missing_candidate_never_changes_grub(self):
        with patch.object(backend, "boot_images", return_value={}):
            with self.assertRaises(backend.DebianKernelError):
                backend.stage_one_shot("6.1.0-missing", runner=lambda *a, **k: self.fail("must not run"))


if __name__ == "__main__":
    unittest.main()
