import unittest
from unittest.mock import patch

from lksu import cli, core


class TurkishUiTests(unittest.TestCase):
    def tearDown(self):
        cli._set_ui_language("en")

    def test_server_name_error_is_localized(self):
        cli._set_ui_language("tr")
        error = cli._ui_error("Invalid server name: use up to 80 letters, numbers, spaces, dots, parentheses or hyphens")
        self.assertIn("Geçersiz sunucu adı", str(error))

    def test_self_update_prompt_is_localized(self):
        cli._set_ui_language("tr")
        self.assertEqual(cli._ui("Automatic LKSU application updates: "), "Otomatik LKSU uygulama güncellemeleri: ")

    def test_english_remains_unchanged(self):
        cli._set_ui_language("en")
        self.assertEqual(cli._ui("Automatic LKSU application updates: "), "Automatic LKSU application updates: ")

    def test_turkish_yes_no_accepts_e_and_h(self):
        cli._set_ui_language("tr")
        with patch("builtins.input", return_value="e"):
            self.assertTrue(cli.yes_no("Automatically install kernel updates?", False))
        with patch("builtins.input", return_value="h"):
            self.assertFalse(cli.yes_no("Automatically install kernel updates?", True))


if __name__ == "__main__":
    unittest.main()
