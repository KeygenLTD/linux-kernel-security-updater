import importlib.util
import pathlib
import tempfile
import unittest

MODULE = pathlib.Path(__file__).resolve().parent / "vm" / "guest-grub-select.py"
spec = importlib.util.spec_from_file_location("guest_grub_select", MODULE)
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)


class GrubSelectionTests(unittest.TestCase):
    def test_nested_submenu_and_kernel(self):
        config = """submenu 'Advanced options for Debian' $menuentry_id_option 'advanced-abc' {
 menuentry 'Debian GNU/Linux, with Linux 6.1.0-55-amd64' --class debian --id 'gnulinux-6.1.0-55-amd64-advanced-abc' {
  linux /boot/vmlinuz-6.1.0-55-amd64 root=/dev/vda1 ro
 }
 menuentry 'Debian GNU/Linux, with Linux 6.1.0-54-cloud-amd64' --id 'gnulinux-6.1.0-54-cloud-amd64-advanced-abc' {
  linux /boot/vmlinuz-6.1.0-54-cloud-amd64 root=/dev/vda1 ro
 }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "grub.cfg"
            path.write_text(config)
            self.assertEqual(selector.choose("6.1.0-55-amd64", str(path)),
                             "advanced-abc>gnulinux-6.1.0-55-amd64-advanced-abc")
            self.assertEqual(selector.choose("6.1.0-54-cloud-amd64", str(path)),
                             "advanced-abc>gnulinux-6.1.0-54-cloud-amd64-advanced-abc")

    def test_missing_kernel_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "grub.cfg"
            path.write_text("menuentry 'Debian' {\n linux /vmlinuz-6.1.0-1-amd64 ro\n}\n")
            with self.assertRaisesRegex(ValueError, "No GRUB entry"):
                selector.choose("6.1.0-55-amd64", str(path))

    def test_invalid_release_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid kernel"):
            selector.choose("../../etc/passwd")


if __name__ == "__main__":
    unittest.main()
