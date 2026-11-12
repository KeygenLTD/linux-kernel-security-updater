import pathlib
import tempfile
import unittest
from unittest.mock import patch
from lksu import debian_backend as backend


class DebianBackendTests(unittest.TestCase):
    def test_vendor_package_selection(self):
        self.assertEqual(backend.kernel_package("debian"), "linux-image-amd64")
        self.assertEqual(backend.kernel_package("ubuntu"), "linux-image-generic")
        self.assertEqual(backend.kernel_package("ubuntu", "virtual"), "linux-image-virtual")
        with self.assertRaises(backend.DebianKernelError):
            backend.kernel_package("rocky")
        with self.assertRaises(backend.DebianKernelError):
            backend.kernel_package("ubuntu", "custom")

    def test_candidate_requires_preserved_old_image(self):
        before = {"6.1.0-old": object()}
        after = {"6.1.0-old": object(), "6.1.0-new": object()}
        self.assertEqual(backend.select_candidate(before, after, "6.1.0-old"), "6.1.0-new")
        with self.assertRaises(backend.DebianKernelError):
            backend.select_candidate(before, {"6.1.0-new": object()}, "6.1.0-old")
        with self.assertRaises(backend.DebianKernelError):
            backend.select_candidate(before, before, "6.1.0-old")

    def test_no_apt_transaction_if_running_kernel_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(backend, "boot_images", return_value={}):
                called = []
                with self.assertRaises(backend.DebianKernelError):
                    backend.install_kernel("debian", "6.1.0-old", runner=lambda *a, **k: called.append(a))
                self.assertFalse(called)

    def test_install_does_not_reboot_or_remove_kernels(self):
        old = {"6.1.0-old": pathlib.Path("/boot/vmlinuz-6.1.0-old")}
        new = dict(old, **{"6.1.0-new": pathlib.Path("/boot/vmlinuz-6.1.0-new")})
        commands = []
        class Result:
            returncode = 0
        def runner(args, **kwargs):
            commands.append(args)
            return Result()
        with patch.object(backend, "boot_images", side_effect=[old, new]):
            result = backend.install_kernel("debian", "6.1.0-old", runner=runner)
        self.assertEqual(result["candidate"], "6.1.0-new")
        self.assertEqual(commands, [
            ["apt-get", "update", "-qq"],
            ["apt-get", "install", "-y", "--no-install-recommends", "linux-image-amd64"]])


if __name__ == "__main__":
    unittest.main()
