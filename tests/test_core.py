import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lksu import core


class KernelTests(unittest.TestCase):
    def test_check_rejects_unexpected_repoquery_output(self):
        with patch.object(core, "preflight", return_value={"running": "old"}), patch.object(
            core, "run", return_value=type("P", (), {"returncode": 0, "stdout": "bogus output", "stderr": ""})()
        ):
            with self.assertRaises(core.LKSUError):
                core.check()

    def test_apply_rejects_security_only_policy(self):
        with self.assertRaises(core.LKSUError):
            core.apply("security-only")

    def test_apply_preserves_running_kernel_and_records_pending(self):
        with tempfile.TemporaryDirectory(dir=".") as temp:
            state = Path(temp) / "state.json"
            with patch.object(core, "STATE", state), patch.object(core, "check", return_value={
                "running": "old", "updates": [{"name": "kernel-core", "evr": "new", "arch": "x86_64"}]
            }), patch.object(core, "run") as run, patch.object(core, "installed", return_value=["old", "new"]), patch.object(
                core, "default_kernel", return_value="/boot/vmlinuz-new"
            ), patch.object(core.Path, "exists", autospec=True, side_effect=lambda path: str(path).replace("\\", "/").endswith("/boot/vmlinuz-old")):
                result = core.apply("all-stable")
            self.assertEqual(result["status"], "installed-awaiting-manual-reboot")
            self.assertTrue(json.loads(state.read_text())["pending"])
            self.assertEqual(run.call_args.args[:4], ("dnf", "-y", "--setopt=installonly_limit=0", "upgrade"))

    def test_verify_failure_keeps_pending_state(self):
        with tempfile.TemporaryDirectory(dir=".") as temp:
            state = Path(temp) / "state.json"
            state.write_text(json.dumps({"pending": True, "old_kernel": "old", "new_default": "/boot/vmlinuz-new"}))
            with patch.object(core, "STATE", state), patch.object(core.os, "uname", create=True, return_value=type("U", (), {"release": "new"})()), patch.object(
                core, "run", return_value=type("P", (), {"returncode": 1})()
            ):
                result = core.verify(["lsws"])
            self.assertFalse(result["healthy"])
            self.assertTrue(json.loads(state.read_text())["pending"])


if __name__ == "__main__":
    unittest.main()
