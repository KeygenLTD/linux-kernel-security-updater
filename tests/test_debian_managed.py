import pathlib
import tempfile
import unittest
from unittest.mock import patch
from lksu import debian_backend as backend


class ManagedDebianTests(unittest.TestCase):
    def test_apply_persists_pending_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = pathlib.Path(tmp) / "state.json"
            with patch.object(backend, "install_kernel", return_value={
                "previous": "6.1-old", "candidate": "6.1-new", "package": "linux-image-amd64"}):
                result = backend.apply_managed("debian", "6.1-old", state)
            self.assertTrue(result["pending"])
            self.assertIn('"old_kernel": "6.1-old"', state.read_text())
            with self.assertRaises(backend.DebianKernelError):
                backend.apply_managed("debian", "6.1-old", state)

    def test_verify_keeps_pending_on_failed_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = pathlib.Path(tmp) / "state.json"
            with patch.object(backend, "install_kernel", return_value={
                "previous": "6.1-old", "candidate": "6.1-new", "package": "linux-image-amd64"}):
                backend.apply_managed("debian", "6.1-old", state)
            failed = backend.verify_managed(state, "6.1-new", False)
            self.assertFalse(failed["healthy"])
            self.assertIn('"pending": true', state.read_text())
            passed = backend.verify_managed(state, "6.1-new", True)
            self.assertTrue(passed["healthy"])
            self.assertIn('"pending": false', state.read_text())


if __name__ == "__main__":
    unittest.main()
