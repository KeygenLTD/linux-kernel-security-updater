import unittest
from lksu.backend_dispatch import backend_plan
from lksu.distributions import Distribution


class BackendDispatchTests(unittest.TestCase):
    def test_only_exact_verified_almalinux_releases_enable_update(self):
        for version in ("8.10", "9.8", "10.1"):
            d = Distribution("almalinux", version, "rhel", "dnf/rpm",
                             "rpm-kernel", "grubby/grub2-reboot",
                             "enabled", "guarded", "validated existing backend")
            p = backend_plan(d)
            self.assertEqual(p["backend"], "almalinux-rpm-grub")
            self.assertTrue(p["guarded_trial_reboot"])

    def test_unverified_distributions_cannot_fall_through_to_almalinux(self):
        for name, family, manager in (
            ("cloudlinux", "cloudlinux", "dnf/rpm"),
            ("rocky", "rhel", "dnf/rpm"),
            ("rhel", "rhel", "dnf/rpm"),
            ("ubuntu", "debian", "apt/dpkg"),
            ("debian", "debian", "apt/dpkg"),
            ("arch", "arch", "pacman"),
            ("almalinux", "rhel", "dnf/rpm"),
        ):
            d = Distribution(name, "11", family, manager, "not-validated",
                             "not-validated", "blocked", "blocked", "unverified")
            p = backend_plan(d)
            self.assertIsNone(p["backend"])
            self.assertFalse(p["automatic_kernel_install"])
            self.assertFalse(p["guarded_trial_reboot"])


if __name__ == "__main__":
    unittest.main()
