import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lksu import core, self_update


class WheelResponse(io.BytesIO):
    def geturl(self):
        return "https://release-assets.githubusercontent.com/objects/release.whl"

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class SelfUpdateTests(unittest.TestCase):
    def test_version_parsing_rejects_untrusted_tag_formats(self):
        self.assertEqual(self_update.version_tuple("v0.3.12"), (0, 3, 12))
        for value in ("main", "v0.3.12-rc1", "v0.3.12/evil", "v00.3.12"):
            with self.subTest(tag=value), self.assertRaises(core.LKSUError):
                self_update.version_tuple(value)

    def test_release_requires_server_sha256_digest(self):
        release = {
            "tag_name": "v0.3.12", "draft": False, "prerelease": False,
            "assets": [{
                "name": "lksu-0.3.12-py3-none-any.whl",
                "state": "uploaded", "size": 100,
                "digest": "",
                "browser_download_url": "https://github.com/KeygenLTD/linux-kernel-security-updater/releases/download/v0.3.12/lksu-0.3.12-py3-none-any.whl",
            }]
        }
        with patch.object(self_update, "_json", return_value=release):
            with self.assertRaisesRegex(core.LKSUError, "SHA-256"):
                self_update.release_info()
        release["assets"][0]["digest"] = "sha256:" + "a" * 64
        with patch.object(self_update, "_json", return_value=release):
            info = self_update.release_info()
        self.assertEqual(info["tag"], "v0.3.12")
        self.assertEqual(info["sha256"], "a" * 64)

    def test_download_rejects_bad_sha256(self):
        data = b"not-a-real-wheel"
        with tempfile.TemporaryDirectory() as folder, patch.object(
            self_update.urllib.request, "urlopen", return_value=WheelResponse(data)
        ):
            with self.assertRaisesRegex(core.LKSUError, "SHA-256"):
                self_update._download({
                    "url": "https://github.com/KeygenLTD/linux-kernel-security-updater/releases/download/v0.3.12/lksu-0.3.12-py3-none-any.whl",
                    "size": len(data), "sha256": "f" * 64
                }, Path(folder) / "wheel.whl")

    def test_download_accepts_exact_sha256(self):
        data = b"test fixture only, not an installable wheel"
        with tempfile.TemporaryDirectory() as folder, patch.object(
            self_update.urllib.request, "urlopen", return_value=WheelResponse(data)
        ):
            path = Path(folder) / "wheel.whl"
            self_update._download({
                "url": "https://github.com/KeygenLTD/linux-kernel-security-updater/releases/download/v0.3.12/lksu-0.3.12-py3-none-any.whl",
                "size": len(data), "sha256": hashlib.sha256(data).hexdigest()
            }, path)
            self.assertEqual(path.read_bytes(), data)

    def test_scheduled_self_update_disabled_does_not_contact_network(self):
        with patch.object(self_update, "release_info") as network, patch.object(
            self_update, "installed_version", return_value="v0.3.11"
        ):
            result = self_update.update(automatic=True, enabled=False)
        self.assertEqual(result["status"], "self-update-disabled")
        network.assert_not_called()

    def test_self_update_refuses_nonroot(self):
        with patch.object(self_update.os, "geteuid", return_value=1000):
            with self.assertRaisesRegex(core.LKSUError, "Root"):
                self_update.update()

    def test_unmanaged_development_install_blocks_self_update_before_network(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "lksu"
            binary = Path(folder) / "bin"
            root.mkdir()
            binary.mkdir()
            development = Path(folder) / "development"
            (development / "bin").mkdir(parents=True)
            (development / "bin" / "lksu").write_text("#!/bin/sh\\n")
            (binary / "lksu").symlink_to(development / "bin" / "lksu")
            with patch.object(self_update, "ROOT", root), patch.object(self_update, "BIN_DIR", binary), patch.object(
                self_update, "release_info"
            ) as network, patch.object(self_update.os, "geteuid", return_value=0):
                with self.assertRaisesRegex(core.LKSUError, "Unmanaged"):
                    self_update.update()
                network.assert_not_called()

    def test_legacy_entrypoints_restored_if_new_lksu_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root, binary = Path(folder) / "root", Path(folder) / "bin"
            root.mkdir()
            binary.mkdir()
            (binary / "lksu").write_text("#!/bin/sh\necho old\n")
            (binary / "lksu-fleet").write_text("#!/bin/sh\necho old-fleet\n")
            candidate = root / "releases" / "v0.3.12"
            candidate.mkdir(parents=True)
            with patch.object(self_update, "ROOT", root), patch.object(self_update, "BIN_DIR", binary), patch.object(
                self_update, "_cmd", side_effect=core.LKSUError("new executable failed")
            ):
                with self.assertRaises(core.LKSUError):
                    self_update._activate_release(candidate)
            self.assertFalse((root / "current").exists())
            self.assertFalse((binary / "lksu").is_symlink())
            self.assertIn("echo old", (binary / "lksu").read_text())
            self.assertIn("echo old-fleet", (binary / "lksu-fleet").read_text())


if __name__ == "__main__":
    unittest.main()
