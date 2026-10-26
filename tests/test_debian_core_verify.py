import unittest
from unittest.mock import patch
from lksu import core


class DebianCoreVerifyDispatchTests(unittest.TestCase):
    def test_debian_state_uses_debian_verifier_not_grubby(self):
        state = {"backend": "debian-apt-grub", "pending": True,
                 "old_kernel": "6.1-old", "new_default": "/boot/vmlinuz-6.1-new"}
        cfg = {"services": ["ssh"]}
        with patch.object(core, "pending_update", return_value=state), \
             patch("lksu.health.check_all", return_value={"service:ssh": True}), \
             patch("lksu.debian_backend.verify_managed",
                   return_value={"healthy": True, "status": "verified"}) as verify, \
             patch.object(core, "run") as runner:
            result = core.verify(cfg)
        self.assertTrue(result["healthy"])
        self.assertTrue(result["verification_performed"])
        verify.assert_called_once()
        runner.assert_not_called()

    def test_failed_health_still_dispatches_and_marks_unhealthy(self):
        state = {"backend": "debian-apt-grub", "pending": True}
        with patch.object(core, "pending_update", return_value=state), \
             patch("lksu.health.check_all", return_value={"service:ssh": False}), \
             patch("lksu.debian_backend.verify_managed",
                   return_value={"healthy": False, "status": "operator-recovery-required"}) as verify:
            result = core.verify({"services": ["ssh"]})
        self.assertFalse(result["healthy"])
        self.assertFalse(verify.call_args.args[2])


if __name__ == "__main__":
    unittest.main()
