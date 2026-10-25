"""Regression tests for root-only file and updater safety policies."""
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lksu import core, fleet, self_update


class PrivilegedHostHardening(unittest.TestCase):
    def test_subprocess_drops_environment_injection(self):
        env = {
            "PATH": "/tmp/rogue", "PYTHONPATH": "/tmp/module", "PYTHONHOME": "/tmp/python",
            "LD_PRELOAD": "/tmp/lib.so", "LD_LIBRARY_PATH": "/tmp",
            "BASH_ENV": "/tmp/evil", "ENV": "/tmp/evil", "HOME": "/root",
        }
        with patch.dict(os.environ, env), patch("lksu.core.subprocess.run") as run:
            run.return_value.returncode = 0
            core.run("rpm", "--version")
        child = run.call_args.kwargs["env"]
        self.assertEqual(child["PATH"], "/usr/sbin:/usr/bin:/sbin:/bin")
        self.assertNotIn("LD_PRELOAD", child)
        self.assertNotIn("PYTHONPATH", child)
        self.assertNotIn("BASH_ENV", child)
        self.assertEqual(child["HOME"], "/root")

    def test_config_rejects_symlink_or_world_readable_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            secret = base / "real.json"
            secret.write_text('{"email":"x"}')
            secret.chmod(0o600)
            linked = base / "config.json"
            linked.symlink_to(secret)
            with patch.object(core, "CONFIG", linked):
                with self.assertRaisesRegex(core.LKSUError, "regular file"):
                    core.config()
            secret.chmod(0o644)
            with patch.object(core, "CONFIG", secret):
                with self.assertRaises(core.LKSUError):
                    core.config()

    def test_atomic_state_writer_protects_mode_and_random_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "state" / "data.json"
            core.save(dest, {"pending": False})
            self.assertEqual(stat.S_IMODE(dest.stat().st_mode), 0o600)
            self.assertEqual(dest.read_text().strip(), '{\n  "pending": false\n}')
            self.assertEqual([x for x in dest.parent.iterdir() if x.name != dest.name], [])

    def test_state_writer_rejects_symlinked_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "actual").mkdir()
            (base / "linked").symlink_to(base / "actual", target_is_directory=True)
            with self.assertRaisesRegex(core.LKSUError, "linked"):
                core.save(base / "linked" / "state.json", {"x": 1})

    def test_self_update_subprocess_drops_inherited_python_hooks(self):
        with patch.dict(os.environ, {"PYTHONPATH": "/tmp/injected", "LD_PRELOAD": "/tmp/lib.so", "PIP_CONFIG_FILE": "/tmp/pip.conf"}), patch(
            "lksu.self_update.subprocess.run"
        ) as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "0.3.17\n"
            self_update._cmd("/usr/bin/python3", "-V")
        child = run.call_args.kwargs["env"]
        for key in ("PYTHONPATH", "LD_PRELOAD", "PIP_CONFIG_FILE"):
            self.assertNotIn(key, child)

    def test_self_update_rejects_symlinked_root(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "legit").mkdir()
            (base / "link").symlink_to(base / "legit", target_is_directory=True)
            with patch.object(self_update, "ROOT", base / "link"), patch.object(
                self_update.os, "geteuid", return_value=0
            ):
                with self.assertRaisesRegex(core.LKSUError, "linked"):
                    self_update.update()

    def test_fleet_blocks_plaintext_remote_telemetry(self):
        with patch("lksu.fleet.urllib.request.urlopen") as network:
            for url in ("http://remote.example:9443", "ftp://remote.example", "https://u:p@remote.example"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    fleet.send_report({"fleet": {
                        "url": url, "server_id": "node-1", "secret": "placeholder",
                    }}, {"status": "updated"})
            network.assert_not_called()

    def test_fleet_accepts_explicit_https(self):
        with patch("lksu.fleet.urllib.request.urlopen") as network:
            network.return_value.__enter__.return_value.status = 202
            result = fleet.send_report({"fleet": {
                "url": "https://fleet.example:9443", "server_id": "node-1", "secret": "placeholder",
            }}, {"status": "updated"})
        self.assertEqual(result, 202)
        self.assertTrue(network.call_args.args[0].full_url.startswith("https://"))


if __name__ == "__main__":
    unittest.main()
