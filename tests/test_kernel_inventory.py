import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lksu import core
from lksu.distributions import Distribution
from lksu.kernel_inventory import apt_inventory, rpm_inventory


def distro(identifier, family, manager):
    return Distribution(identifier, "9", family, manager, "none", "none", "blocked", "blocked", "test")


class KernelInventoryTests(unittest.TestCase):
    def test_apt_inventory_ignores_removed_and_non_kernel_packages(self):
        output = ("linux-image-6.8.0-52-generic install ok installed 6.8.0-52.53\n"
                  "linux-image-generic install ok installed 6.8.0.52.52\n"
                  "linux-image-6.1.0-1-amd64 deinstall ok config-files 6.1.0-1\n"
                  "other-package install ok installed 1.0\n")
        proc = SimpleNamespace(returncode=0, stdout=output, stderr="")
        with patch.object(core, "run", return_value=proc) as runner, patch.object(core.os, "uname", return_value=SimpleNamespace(release="6.8.0-52-generic")):
            result = apt_inventory(distro("ubuntu", "debian", "apt/dpkg"))
        self.assertEqual(len(result["installed_kernel_packages"]), 2)
        self.assertEqual(result["automatic_reboot"], "blocked")
        self.assertEqual(runner.call_args.args[0], "dpkg-query")
        self.assertTrue(runner.call_args.kwargs["check"] is False)

    def test_rpm_inventory_reports_kernel_without_mutation(self):
        output = ("kernel-core 5.14.0-1.el9.x86_64\n"
                  "kernel-uek 5.15.0-1.el9.x86_64\n"
                  "kernel-lve 4.18.0-1.el8.x86_64\n"
                  "bash 5.0-1.x86_64\n")
        with patch.object(core, "run", return_value=SimpleNamespace(returncode=0, stdout=output, stderr="")), patch.object(core.os, "uname", return_value=SimpleNamespace(release="5.14.0")):
            result = rpm_inventory(distro("cloudlinux", "cloudlinux", "dnf/rpm"))
        self.assertEqual({p["name"] for p in result["installed_kernel_packages"]}, {"kernel-core", "kernel-uek", "kernel-lve"})
        self.assertEqual(result["automatic_updates"], "blocked")

    def test_apt_rejects_incompatible_distro(self):
        with self.assertRaises(core.LKSUError):
            apt_inventory(distro("arch", "arch", "pacman"))

    def test_rpm_rejects_incompatible_distro(self):
        with self.assertRaises(core.LKSUError):
            rpm_inventory(distro("debian", "debian", "apt/dpkg"))


if __name__ == "__main__":
    unittest.main()
