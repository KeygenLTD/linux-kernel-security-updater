import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lksu import core
from lksu.distributions import detect, parse_os_release, require_automatic_kernel_backend


class DistributionTests(unittest.TestCase):
    def identify(self, value):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "os-release"
            target.write_text(value)
            return detect(target)

    def test_almalinux_compatible_and_original_gate_retained(self):
        for major in ("8", "9", "10"):
            host = self.identify('ID=almalinux\nVERSION_ID="'+major+'.1"\n')
            self.assertEqual(host.update_capability, "enabled")
            self.assertEqual(require_automatic_kernel_backend(host), host)

    def test_other_linux_distributions_detected_but_not_unsafely_enabled(self):
        matrix = {"rocky": "dnf/rpm", "rhel": "dnf/rpm", "centos": "dnf/rpm",
                  "fedora": "dnf/rpm", "ubuntu": "apt/dpkg", "debian": "apt/dpkg",
                  "arch": "pacman"}
        for distro, package_manager in matrix.items():
            with self.subTest(distro=distro):
                host = self.identify("ID="+distro+"\nVERSION_ID=9\n")
                self.assertEqual(host.package_manager, package_manager)
                self.assertEqual(host.reboot_capability, "blocked")
                with self.assertRaises(core.LKSUError):
                    require_automatic_kernel_backend(host)

    def test_unknown_linux_distribution_fails_closed(self):
        host = self.identify("ID=unknownos\nVERSION_ID=1\n")
        self.assertEqual(host.family, "unknown")
        with self.assertRaises(core.LKSUError):
            require_automatic_kernel_backend(host)

    def test_release_file_quoting_and_comments(self):
        values = parse_os_release("# comment\nID='ubuntu'\nVERSION_ID=\"24.04\"\n")
        self.assertEqual(values, {"ID": "ubuntu", "VERSION_ID": "24.04"})

    def test_almalinux_new_unverified_major_fails_closed(self):
        host = self.identify("ID=almalinux\nVERSION_ID=11.0\n")
        self.assertEqual(host.update_capability, "unsupported")
        with self.assertRaises(core.LKSUError):
            require_automatic_kernel_backend(host)

    def test_original_os_version_uses_explicit_backend_gate(self):
        target = self.identify("ID=almalinux\nVERSION_ID=9.8\n")
        with patch("lksu.distributions.detect", return_value=target):
            self.assertEqual(core.os_version(), "9.8")
        other = self.identify("ID=ubuntu\nVERSION_ID=24.04\n")
        with patch("lksu.distributions.detect", return_value=other):
            with self.assertRaisesRegex(core.LKSUError, "not supported"):
                core.os_version()


if __name__ == "__main__":
    unittest.main()
