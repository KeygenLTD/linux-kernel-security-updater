"""Regression coverage for LKSU verification racing with scheduled maintenance."""
import contextlib
import fcntl
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lksu import cli, core


ROOT = Path(__file__).resolve().parents[1]


class BootVerificationOrderingTests(unittest.TestCase):
    def test_systemd_maintenance_queues_boot_verification_first(self):
        maintenance = (ROOT / "systemd/lksu-maintenance.service").read_text()
        self.assertIn("After=network-online.target lksu-verify.service", maintenance)
        self.assertIn("Wants=network-online.target lksu-verify.service", maintenance)
        verify = (ROOT / "systemd/lksu-verify.service").read_text()
        self.assertIn("ConditionPathExists=/var/lib/lksu/state.json", verify)

    def test_security_watch_prepares_private_state_before_namespace(self):
        unit = (ROOT / "systemd/lksu-security-watch.service").read_text()
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("StateDirectory=lksu", unit)
        self.assertIn("StateDirectoryMode=0700", unit)
        self.assertIn("ReadWritePaths=/var/lib/lksu", unit)
        installer = (ROOT / "install.sh").read_text()
        self.assertIn("install -d -o root -g root -m 0700 /var/lib/lksu", installer)
        self.assertLess(installer.index("install -d -o root -g root -m 0700 /var/lib/lksu"),
                        installer.index("systemctl enable --now lksu-self-update.timer"))

    def test_default_kernel_operation_does_not_wait_for_busy_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "kernel.lock"
            with path.open("a+") as held:
                fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.object(core, "KERNEL_LOCK", path):
                    with self.assertRaisesRegex(core.LKSUError, "Another LKSU kernel operation"):
                        with core.kernel_operation_lock():
                            self.fail("A second writer acquired an occupied lock")
                fcntl.flock(held.fileno(), fcntl.LOCK_UN)

    def test_boot_verification_waits_then_acquires_released_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "kernel.lock"
            original_flock = core.fcntl.flock
            attempts = []

            def busy_once(fd, flags):
                if flags & fcntl.LOCK_NB:
                    attempts.append(flags)
                    if len(attempts) == 1:
                        raise BlockingIOError("busy")
                return original_flock(fd, flags)

            with patch.object(core, "KERNEL_LOCK", path), \
                 patch.object(core.fcntl, "flock", side_effect=busy_once), \
                 patch.object(core.time, "sleep") as sleep:
                with core.kernel_operation_lock(wait_seconds=5):
                    self.assertEqual(len(attempts), 2)
                sleep.assert_called_once()

    def test_verify_cli_waits_for_timer_lock(self):
        with patch.object(cli.core, "config", return_value={"notifications": False}), \
             patch.object(cli.core, "kernel_operation_lock") as lock, \
             patch.object(cli.core, "verify", return_value={
                 "status": "no-pending-verification", "healthy": True,
                 "verification_performed": False}), \
             patch.object(cli.notifications, "send_event"), \
             patch.object(cli, "send_fleet_report"):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["verify"]), 0)
        lock.assert_called_once_with(wait_seconds=120)

    def test_readme_uses_fixed_release_independent_install_address(self):
        text = (ROOT / "README.md").read_text()
        self.assertIn("KeygenLTD/linux-kernel-security-updater/main/bootstrap.sh", text)
        bootstrap = (ROOT / "bootstrap.sh").read_text()
        self.assertIn('RELEASE="v0.3.22"', bootstrap)
        self.assertIn("LKSU stable bootstrap: installing pinned release", bootstrap)


if __name__ == "__main__":
    unittest.main()
