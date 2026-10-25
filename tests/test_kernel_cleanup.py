import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lksu import core, kernel_cleanup


RUNNING = "5.14.0-687.31.1.el9_8.x86_64"
FALLBACK = "5.14.0-687.12.1.el9_8.x86_64"
ANCIENT = "5.14.0-611.49.1.el9_7.x86_64"
MIB = 1024 * 1024


def process(stdout="", returncode=0, stderr=""):
    return type("P", (), {"stdout": stdout, "returncode": returncode, "stderr": stderr})()


def disk(free):
    return type("Usage", (), {"free": free})()


class SafeKernelCleanupTests(unittest.TestCase):
    def test_no_cleanup_if_boot_free(self):
        with patch.object(kernel_cleanup.shutil, "disk_usage", return_value=disk(671 * MIB)), patch.object(
            core, "run"
        ) as run:
            self.assertEqual(kernel_cleanup.reclaim_for_update(), [])
            run.assert_not_called()

    def test_automatically_removes_only_oldest_exact_kernel_packages(self):
        rpm_erasures = []
        dnf_removals = []
        def fake_run(*args, **kwargs):
            if args[:2] == ("rpm", "-q") and args[-1] == "kernel-core":
                # Ordered oldest, fallback, current.
                return process(
                    ANCIENT + " 100\\n" + FALLBACK + " 200\\n" + RUNNING + " 300\\n"
                )
            if args[:2] == ("rpm", "-q"):
                candidate = args[-1]
                if candidate.endswith(ANCIENT) and not candidate.startswith("kernel-modules-extra-"):
                    return process(candidate + "\\n")
                return process(returncode=1)
            if args[:3] == ("rpm", "-e", "--test"):
                rpm_erasures.append(args)
                return process()
            if args[0] == "dnf":
                dnf_removals.append(args)
                return process()
            raise AssertionError("Unexpected command: " + str(args))
        with tempfile.TemporaryDirectory() as folder, patch.object(
            core, "STATE", Path(folder) / "state.json"
        ), patch.object(kernel_cleanup.shutil, "disk_usage", side_effect=[
            disk(480 * MIB), disk(650 * MIB)
        ]), patch.object(core.os, "uname", return_value=type(
            "U", (), {"release": RUNNING, "machine": "x86_64"}
        )()), patch.object(core, "run", side_effect=fake_run), patch.object(
            core, "default_kernel", return_value="/boot/vmlinuz-" + RUNNING
        ), patch.object(core, "pending_update", return_value=None), patch.object(
            core, "installed", return_value=[FALLBACK, RUNNING]):
            removed = kernel_cleanup.reclaim_for_update()
        self.assertEqual(removed, [ANCIENT])
        self.assertEqual(len(rpm_erasures), 1)
        self.assertEqual(len(dnf_removals), 1)
        self.assertEqual(len(dnf_removals[0]), 10)
        self.assertTrue(all(target.endswith(ANCIENT) for target in dnf_removals[0][-4:]))
        self.assertNotIn(RUNNING, " ".join(dnf_removals[0]))
        self.assertNotIn(FALLBACK, " ".join(dnf_removals[0]))

    def test_low_space_with_only_two_kernels_refuses_cleanup(self):
        with patch.object(kernel_cleanup.shutil, "disk_usage", return_value=disk(250 * MIB)), patch.object(
            kernel_cleanup, "_kernel_core_install_times", return_value={FALLBACK: 100, RUNNING: 200}
        ), patch.object(kernel_cleanup, "_protected_releases", return_value={FALLBACK, RUNNING}), patch.object(
            core, "run"
        ) as run:
            with self.assertRaisesRegex(core.LKSUError, "only two installed kernels remain"):
                kernel_cleanup.reclaim_for_update()
            run.assert_not_called()

    def test_running_default_mismatch_refuses_cleanup(self):
        with patch.object(core.os, "uname", return_value=type(
            "U", (), {"release": RUNNING}
        )()), patch.object(core, "default_kernel", return_value="/boot/vmlinuz-" + FALLBACK):
            with self.assertRaisesRegex(core.LKSUError, "GRUB default"):
                kernel_cleanup._protected_releases({ANCIENT: 100, FALLBACK: 200, RUNNING: 300})

    def test_pending_kernel_update_refuses_cleanup(self):
        with patch.object(core.os, "uname", return_value=type(
            "U", (), {"release": RUNNING}
        )()), patch.object(core, "default_kernel", return_value="/boot/vmlinuz-" + RUNNING), patch.object(
            core, "pending_update", return_value={"pending": True}
        ):
            with self.assertRaisesRegex(core.LKSUError, "pending verification"):
                kernel_cleanup._protected_releases({ANCIENT: 100, FALLBACK: 200, RUNNING: 300})

    def test_all_protected_kernels_refuse_cleanup(self):
        with patch.object(kernel_cleanup.shutil, "disk_usage", return_value=disk(450 * MIB)), patch.object(
            kernel_cleanup, "_kernel_core_install_times", return_value={
                ANCIENT: 100, FALLBACK: 200, RUNNING: 300
            }
        ), patch.object(kernel_cleanup, "_protected_releases", return_value={
            ANCIENT, FALLBACK, RUNNING
        }), patch.object(core, "run") as run:
            with self.assertRaisesRegex(core.LKSUError, "all remaining kernels are protected"):
                kernel_cleanup.reclaim_for_update()
            run.assert_not_called()

    def test_rpm_dependency_check_must_pass_before_dnf_removal(self):
        with patch.object(kernel_cleanup.shutil, "disk_usage", return_value=disk(450 * MIB)), patch.object(
            kernel_cleanup, "_kernel_core_install_times", return_value={
                ANCIENT: 100, FALLBACK: 200, RUNNING: 300
            }
        ), patch.object(kernel_cleanup, "_protected_releases", return_value={
            FALLBACK, RUNNING
        }), patch.object(kernel_cleanup, "_exact_installed_packages", return_value=[
            "kernel-core-" + ANCIENT
        ]), patch.object(core, "run", side_effect=core.LKSUError("rpm dependency failed")) as run:
            with self.assertRaisesRegex(core.LKSUError, "rpm dependency failed"):
                kernel_cleanup.reclaim_for_update()
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[:3], ("rpm", "-e", "--test"))

    def test_unexpected_exact_package_match_fails_closed(self):
        with patch.object(core, "run", return_value=process(
            "kernel-core-" + RUNNING + "\\n"
        )):
            with self.assertRaisesRegex(core.LKSUError, "Unexpected kernel package match"):
                kernel_cleanup._exact_installed_packages(ANCIENT)

    def test_applying_update_reclaims_space_only_if_needed(self):
        available = {
            "running": RUNNING, "boot_free_mib": 410,
            "updates": [{"name": "kernel-core", "evr": "latest", "arch": "x86_64"}],
            "security_advisories": [],
        }
        with tempfile.TemporaryDirectory() as folder, patch.object(
            core, "STATE", Path(folder) / "state.json"
        ), patch.object(core, "check", return_value=available), patch.object(
            core, "preflight"
        ) as preflight, patch.object(
            core, "installed", return_value=[RUNNING, "new"]
        ), patch.object(core, "default_kernel", return_value="/boot/vmlinuz-new"), patch.object(
            core.Path, "exists", autospec=True,
            side_effect=lambda path: str(path) == "/boot/vmlinuz-" + RUNNING
        ), patch.object(core, "save"), patch.object(core, "run"), patch.object(
            kernel_cleanup, "reclaim_for_update", return_value=[ANCIENT]
        ) as reclaim:
            report = core.apply("all-stable")
        reclaim.assert_called_once_with()
        preflight.assert_called_once_with()
        self.assertEqual(report["cleaned_old_kernels"], [ANCIENT])

    def test_no_update_means_no_cleanup_even_when_space_low(self):
        available = {
            "running": RUNNING, "boot_free_mib": 200,
            "updates": [], "security_advisories": [],
        }
        with patch.object(core, "check", return_value=available), patch.object(
            kernel_cleanup, "reclaim_for_update"
        ) as reclaim:
            report = core.apply("all-stable")
        self.assertEqual(report["status"], "no-updates")
        reclaim.assert_not_called()


if __name__ == "__main__":
    unittest.main()
