import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lksu import core


RUNNING = "6.12.0-211.51.1.el10_2.x86_64"
NEWER = "6.12.0-211.68.1.el10_2.x86_64"
INFO = {
    "running": RUNNING,
    "default": "/boot/vmlinuz-" + NEWER,
    "reboot_required": True,
    "reboot_target": NEWER,
    "boot_status": "different-installed-kernel",
    "updates": [],
    "security_advisories": [],
}


class BootLifecycleTests(unittest.TestCase):
    def test_installed_new_kernel_is_not_confused_with_dnf_upgrade(self):
        with patch.object(core, "installed", return_value=[RUNNING, NEWER]), patch.object(
            core.Path, "is_file", return_value=True
        ):
            result = core.boot_assessment(INFO)
        self.assertEqual(result["boot_status"], "different-installed-kernel")
        self.assertTrue(result["reboot_required"])
        self.assertEqual(result["reboot_target"], NEWER)

    def test_same_running_and_default_kernel_not_reboot_required(self):
        result = core.boot_assessment({"running": RUNNING, "default": "/boot/vmlinuz-" + RUNNING})
        self.assertFalse(result["reboot_required"])

    def test_adopt_preinstalled_kernel_records_fallback_without_reboot(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            with patch.object(core, "STATE", state), patch.object(core, "_is_newer_kernel", return_value=True), patch.object(
                core, "installed", return_value=[RUNNING, NEWER]
            ), patch.object(core.Path, "is_file", return_value=True), patch.object(core, "run") as run:
                result = core.adopt_preinstalled_kernel(INFO)
            self.assertEqual(result["status"], "installed-awaiting-manual-reboot")
            self.assertEqual(result["old_kernel"], RUNNING)
            self.assertEqual(result["new_default"], "/boot/vmlinuz-" + NEWER)
            self.assertTrue(json.loads(state.read_text())["pending"])
            self.assertNotIn(("systemctl", "reboot"), [x.args for x in run.call_args_list])

    def test_adoption_fails_closed_when_kernel_is_older(self):
        with patch.object(core, "pending_update", return_value=None), patch.object(
            core, "_is_newer_kernel", return_value=False
        ):
            with self.assertRaisesRegex(core.LKSUError, "not newer"):
                core.adopt_preinstalled_kernel(INFO)

    def test_automatic_reboot_requires_explicit_recovery_approval(self):
        with self.assertRaisesRegex(core.LKSUError, "recovery_ready"):
            core.auto_reboot_preflight({"automatic_reboot": True, "services": ["lsws"]})

    def test_automatic_reboot_requires_health_checks(self):
        with self.assertRaisesRegex(core.LKSUError, "health checks"):
            core.auto_reboot_preflight({"recovery_ready": True})

    def test_failed_health_checks_block_reboot(self):
        with patch("lksu.health.check_all", return_value={"service:lsws": False}):
            with self.assertRaisesRegex(core.LKSUError, "pre-reboot health"):
                core.auto_reboot_preflight({"recovery_ready": True, "services": ["lsws"]})

    def test_disabled_verify_service_blocks_reboot(self):
        reply = type("P", (), {"returncode": 1, "stdout": "disabled\n"})()
        with patch("lksu.health.check_all", return_value={"service:lsws": True}), patch.object(
            core, "run", return_value=reply
        ):
            with self.assertRaisesRegex(core.LKSUError, "must be enabled"):
                core.auto_reboot_preflight({"recovery_ready": True, "services": ["lsws"]})

    def test_maintenance_adopts_preinstalled_kernel_then_stages_trial(self):
        cfg = {"automatic_updates": True, "automatic_reboot": True, "policy": "all-stable"}
        with patch.object(core, "pending_update", return_value=None), patch.object(
            core, "apply", return_value={"status": "no-updates", **INFO}
        ), patch.object(core, "auto_reboot_preflight"), patch.object(
            core, "adopt_preinstalled_kernel", return_value={
                "status": "installed-awaiting-manual-reboot", "old_kernel": RUNNING
            }
        ) as adopt, patch.object(
            core, "stage_trial_boot", return_value={"trial_entry": "new", "rebooted": False}
        ) as trial:
            result, restart = core.maintenance(cfg)
        self.assertTrue(restart)
        self.assertEqual(result["status"], "trial-boot-staged")
        adopt.assert_called_once()
        trial.assert_called_once()

    def test_no_unattended_reboot_without_reboot_opt_in(self):
        cfg = {"automatic_updates": True, "automatic_reboot": False, "policy": "all-stable"}
        with patch.object(core, "pending_update", return_value=None), patch.object(
            core, "apply", return_value={"status": "no-updates", **INFO}
        ), patch.object(core, "stage_trial_boot") as trial:
            result, restart = core.maintenance(cfg)
        self.assertFalse(restart)
        trial.assert_not_called()

    def test_trial_already_staged_cannot_repeat_boot(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            state.write_text(json.dumps({"pending": True, "trial_entry": "already", "old_kernel": RUNNING}))
            with patch.object(core, "STATE", state), patch.object(core, "run") as run:
                with self.assertRaisesRegex(core.LKSUError, "already staged"):
                    core.stage_trial_boot()
                run.assert_not_called()

    def test_verify_with_no_pending_state_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "missing.json"
            with patch.object(core, "STATE", state):
                result = core.verify({})
            self.assertEqual(result["status"], "no-pending-verification")
            self.assertFalse(result["verification_performed"])

    def test_verify_refuses_to_promote_when_no_health_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            state.write_text(json.dumps({"pending": True, "old_kernel": RUNNING, "new_default": "/boot/vmlinuz-"+NEWER}))
            uname = type("U", (), {"release": NEWER})()
            with patch.object(core, "STATE", state), patch.object(core.os, "uname", return_value=uname), patch(
                "lksu.health.check_all", return_value={}
            ), patch.object(core, "run") as run:
                result = core.verify({})
            self.assertFalse(result["healthy"])
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
