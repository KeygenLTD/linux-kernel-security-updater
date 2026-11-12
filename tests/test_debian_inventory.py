import subprocess
import unittest
from unittest.mock import patch
from lksu import debian_backend


class DebianInventoryTests(unittest.TestCase):
    def test_installed_metapackage(self):
        result = subprocess.CompletedProcess([], 0, "install ok installed", "")
        with patch.object(debian_backend, "boot_images", return_value={"6.1.0-old": object()}), \
             patch.object(debian_backend.subprocess, "run", return_value=result) as runner:
            info = debian_backend.check_host("debian", "6.1.0-old")
        self.assertTrue(info["metapackage_installed"])
        self.assertEqual(info["kernel_metapackage"], "linux-image-amd64")
        self.assertEqual(info["status"], "inventory-only")
        runner.assert_called_once()

    def test_missing_running_kernel_is_rejected_before_package_query(self):
        with patch.object(debian_backend, "boot_images", return_value={}), \
             patch.object(debian_backend.subprocess, "run") as runner:
            with self.assertRaises(debian_backend.DebianKernelError):
                debian_backend.check_host("ubuntu", "6.8.0-1-generic")
            runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
