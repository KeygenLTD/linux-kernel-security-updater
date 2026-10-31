import contextlib
import io
import unittest
from unittest.mock import patch

from lksu import cli, core
from lksu.reporting import format_console_report


CFG = {
    "policy": "all-stable", "automatic_updates": True, "automatic_reboot": False,
    "automatic_lksu_updates": False,
}
CHECKED = {
    "running": "6.12.0-211.51.1.el10_2.x86_64",
    "default": "/boot/vmlinuz-6.12.0-211.68.1.el10_2.x86_64",
    "reboot_target": "6.12.0-211.68.1.el10_2.x86_64",
    "reboot_required": True,
    "updates": [],
    "security_advisories": [{"id": "ALSA-2026:88477", "severity": "Important/Sec.", "cves": ["CVE-2026-1"]}],
}


class ConsoleTests(unittest.TestCase):
    def test_readable_summary_not_json_cve_dump(self):
        with patch("lksu.reporting.os.uname") as uname:
            uname.return_value.nodename = "test-node"
            view = format_console_report(CFG, "scheduled", CHECKED)
        self.assertIn("Status:           REBOOT REQUIRED", view)
        self.assertIn("Running kernel:   6.12.0-211.51.1", view)
        self.assertIn("Next boot kernel: 6.12.0-211.68.1", view)
        self.assertIn("Advisories:       1 listed", view)
        self.assertNotIn("CVE-2026-1", view)
        self.assertNotIn('"updates":', view)
        self.assertIn("Full technical details: lksu scheduled --json", view)

    @patch("lksu.cli.send_fleet_report")
    @patch("lksu.cli.send_report")
    @patch("lksu.cli.core.check", return_value=CHECKED)
    @patch("lksu.cli.core.config", return_value=CFG)
    def test_scheduled_uses_readable_output_by_default(self, _cfg, _check, _send, _fleet):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(cli.main(["scheduled"]), 0)
        self.assertIn("REBOOT REQUIRED", buffer.getvalue())
        self.assertNotIn('"security_advisories":', buffer.getvalue())

    @patch("lksu.cli.send_fleet_report")
    @patch("lksu.cli.send_report")
    @patch("lksu.cli.core.check", return_value=CHECKED)
    @patch("lksu.cli.core.config", return_value=CFG)
    def test_json_flag_preserves_machine_readable_data(self, _cfg, _check, _send, _fleet):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(cli.main(["scheduled", "--json"]), 0)
        self.assertIn('"security_advisories":', buffer.getvalue())
        self.assertIn('"reboot_required": true', buffer.getvalue())

    @patch("lksu.cli.core.save")
    @patch("lksu.cli.core.config", return_value=CFG)
    @patch("lksu.cli.os.geteuid", return_value=0)
    @patch("builtins.input", return_value="")
    def test_upgrade_can_enable_self_updates_without_resetting_mail_settings(self, _input, _root, _config, save):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.configure_self_update()
        saved = save.call_args.args[1]
        self.assertTrue(saved["automatic_lksu_updates"])
        self.assertEqual(saved["policy"], "all-stable")
        self.assertNotIn("maintenance_window", saved)

    @patch("lksu.cli.core.save")
    @patch("lksu.cli.core.config", return_value=CFG)
    @patch("lksu.cli.os.geteuid", return_value=0)
    @patch("builtins.input", return_value="no")
    def test_user_can_decline_self_updates(self, _input, _root, _config, save):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.configure_self_update()
        self.assertFalse(save.call_args.args[1]["automatic_lksu_updates"])


    @patch("lksu.cli.core.save")
    @patch("lksu.cli.core.os_version", return_value="10.2")
    @patch("lksu.cli.os.geteuid", return_value=0)
    @patch("lksu.cli.getpass.getpass", return_value="dedicated-token")
    @patch("builtins.input")
    def test_fresh_install_defaults_to_stable_kernel_automation_and_safe_reboot(
        self, prompt, _token, _root, _os, save
    ):
        prompt.side_effect = lambda label: (
            "en" if "[tr/en]" in label else
            "operator@example.com" if label == "Report email: " else
            "lsws" if label.startswith("Services to verify after reboot") else ""
        )
        with contextlib.redirect_stdout(io.StringIO()):
            cli.setup()
        data = save.call_args.args[1]
        self.assertTrue(data["automatic_updates"])
        self.assertEqual(data["policy"], "all-stable")
        self.assertTrue(data["automatic_lksu_updates"])
        self.assertNotIn("maintenance_window", data)
        self.assertFalse(any("maintenance" in str(call).lower() or "window" in str(call).lower() for call in prompt.call_args_list))
        self.assertTrue(data["automatic_reboot"])
        self.assertFalse(data["recovery_ready"])
        self.assertEqual(data["smtp_password"], "dedicated-token")



    @patch("lksu.cli.detect_active_host_services", return_value=["docker", "nginx", "postgresql"])
    @patch("lksu.cli.core.run")
    @patch("lksu.cli.core.save")
    @patch("lksu.cli.core.config")
    @patch("lksu.cli.os.geteuid", return_value=0)
    @patch("builtins.input")
    def test_automation_offers_active_service_defaults_and_enables_timer(
        self, prompt, _root, config, save, run, discover
    ):
        data = dict(CFG)
        data["services"] = []
        data["health_urls"] = []
        data["recovery_ready"] = True
        data["automatic_reboot"] = True
        config.return_value = data
        def response(message):
            if message.startswith("Services to check"):
                return ""  # Accept detected host services.
            return ""
        prompt.side_effect = response
        run.return_value.returncode = 0
        with contextlib.redirect_stdout(io.StringIO()):
            cli.configure_automation()
        discover.assert_called_once_with()
        self.assertEqual(save.call_args.args[1]["services"], ["docker", "nginx", "postgresql"])
        self.assertTrue(save.call_args.args[1]["automatic_reboot"])
        self.assertIn(
            ("systemctl", "enable", "--now", "lksu-maintenance.timer"),
            [call.args for call in run.call_args_list],
        )

    @patch("lksu.cli.detect_active_host_services", return_value=[])
    @patch("lksu.cli.core.run")
    @patch("lksu.cli.core.save")
    @patch("lksu.cli.core.config")
    @patch("lksu.cli.os.geteuid", return_value=0)
    @patch("builtins.input", return_value="")
    def test_automation_refuses_no_health_checks(
        self, _input, _root, config, save, run, discover
    ):
        data = dict(CFG)
        data["services"] = []
        data["health_urls"] = []
        data["automatic_reboot"] = True
        config.return_value = data
        run.return_value.returncode = 3
        with self.assertRaisesRegex(core.LKSUError, "requires at least one"):
            cli.configure_automation()
        save.assert_not_called()


    @patch("lksu.cli.core.run")
    def test_auto_discovers_generic_services_not_just_web_panels(self, run):
        units = (
            "nginx.service loaded active running Web server\n"
            "postgresql.service loaded active running Database\n"
            "docker.service loaded active running Containers\n"
            "custom-backend.service loaded active running Custom backend\n"
            "lsws.service loaded active running Web server\n"
            "sshd.service loaded active running SSH server\n"
            "systemd-journald.service loaded active running Journal\n"
            "lksu-verify.service loaded active running Kernel verifier\n"
            "dbus-broker.service loaded active running DBus\n"
        )
        def reply(*args, **kwargs):
            response = type("Result", (), {})()
            response.returncode = 0
            if args[1] == "list-units":
                response.stdout = units
            else:
                self.assertEqual(args[1], "is-enabled")
                response.stdout = "enabled\n"
            return response
        run.side_effect = reply
        found = cli.detect_active_host_services()
        self.assertEqual(found, ["custom-backend", "docker", "lsws", "nginx", "postgresql"])
        self.assertNotIn("sshd", found)
        self.assertNotIn("systemd-journald", found)
        self.assertNotIn("lksu-verify", found)

    @patch("lksu.cli.core.run")
    def test_auto_discovers_only_enabled_running_services(self, run):
        def reply(*args, **kwargs):
            response = type("Result", (), {})()
            response.returncode = 0
            if args[1] == "list-units":
                response.stdout = (
                    "nginx.service loaded active running Web server\n"
                    "custom-worker.service loaded active running Worker\n"
                )
            elif args[-1] == "custom-worker.service":
                response.stdout = "disabled\n"
                response.returncode = 1
            else:
                response.stdout = "enabled\n"
            return response
        run.side_effect = reply
        self.assertEqual(cli.detect_active_host_services(), ["nginx"])

    @patch("lksu.cli.detect_active_host_services", return_value=[])
    @patch("lksu.cli.core.run")
    @patch("lksu.cli.core.save")
    @patch("lksu.cli.core.config")
    @patch("lksu.cli.os.geteuid", return_value=0)
    @patch("builtins.input")
    def test_custom_service_works_without_known_panel(
        self, prompt, _root, config, save, run, discover
    ):
        data = dict(CFG)
        data.update({"services": [], "health_urls": [], "automatic_reboot": True, "recovery_ready": True})
        config.return_value = data
        prompt.side_effect = lambda label: "my-worker" if label.startswith("Services to check") else ""
        with contextlib.redirect_stdout(io.StringIO()):
            cli.configure_automation()
        self.assertEqual(save.call_args.args[1]["services"], ["my-worker"])


    @patch("lksu.cli.detect_active_host_services")
    @patch("lksu.cli.core.run")
    @patch("lksu.cli.core.save")
    @patch("lksu.cli.core.config")
    @patch("lksu.cli.os.geteuid", return_value=0)
    @patch("builtins.input")
    def test_replace_existing_service_health_checks_without_mail_reset(
        self, prompt, _root, config, save, run, discover
    ):
        data = dict(CFG)
        data.update({"services": ["old-service"], "health_urls": [],
                     "automatic_reboot": True, "recovery_ready": True,
                     "smtp_password": "retained"})
        config.return_value = data
        prompt.side_effect = lambda label: (
            "nginx,custom-worker" if label.startswith("Services to check") else ""
        )
        with contextlib.redirect_stdout(io.StringIO()):
            cli.configure_automation()
        saved = save.call_args.args[1]
        self.assertEqual(saved["services"], ["nginx", "custom-worker"])
        self.assertEqual(saved["smtp_password"], "retained")
        discover.assert_not_called()
        self.assertIn(
            ("systemctl", "enable", "--now", "lksu-maintenance.timer"),
            [call.args for call in run.call_args_list],
        )

    @patch("lksu.cli.detect_active_host_services", return_value=[])
    @patch("lksu.cli.core.run")
    @patch("lksu.cli.core.save")
    @patch("lksu.cli.core.config")
    @patch("lksu.cli.os.geteuid", return_value=0)
    @patch("builtins.input")
    def test_url_only_health_checks_allowed_with_no_services(
        self, prompt, _root, config, save, run, discover
    ):
        data = dict(CFG)
        data.update({"services": [], "health_urls": [{"url": "https://example.net/health", "status": 200}],
                     "automatic_reboot": True, "recovery_ready": True})
        config.return_value = data
        prompt.side_effect = lambda label: "none" if label.startswith("Services to check") else ""
        with contextlib.redirect_stdout(io.StringIO()):
            cli.configure_automation()
        self.assertEqual(save.call_args.args[1]["services"], [])


    @patch("lksu.cli.core.run")
    @patch("lksu.cli.core.save")
    @patch("lksu.cli.core.config")
    @patch("lksu.cli.os.geteuid", return_value=0)
    @patch("builtins.input")
    def test_legacy_settings_never_restrict_automation(
        self, prompt, _root, config, save, run
    ):
        data = dict(CFG)
        data.update({"automatic_reboot": True, "recovery_ready": True, "services": ["mariadb"], "health_urls": [],
                     "maintenance_window": {"enabled": True, "start": "03:00", "duration_minutes": 60}})
        config.return_value = data
        prompt.return_value = ""
        with contextlib.redirect_stdout(io.StringIO()):
            cli.configure_automation()
        saved = save.call_args.args[1]
        self.assertNotIn("maintenance_window", saved)
        self.assertFalse(any("maintenance" in str(call).lower() or "window" in str(call).lower() for call in prompt.call_args_list))
        self.assertTrue(saved["automatic_reboot"])
        self.assertTrue(saved["recovery_ready"])
        self.assertIn(
            ("systemctl", "enable", "--now", "lksu-maintenance.timer"),
            [call.args for call in run.call_args_list],
        )


if __name__ == "__main__":
    unittest.main()

class StatusCommandTests(unittest.TestCase):
    @patch("lksu.cli.core.config", return_value={**CFG, "report_language": "tr"})
    @patch("lksu.cli.core.run")
    def test_active_reads_real_timer_and_shows_turkish(self, run, config):
        from types import SimpleNamespace
        run.side_effect = [
            SimpleNamespace(returncode=0, stdout="active\\n"),
            SimpleNamespace(returncode=0, stdout="enabled\\n"),
        ]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(cli.main(["active"]), 0)
        self.assertIn("ETKİN", buffer.getvalue())
        self.assertIn("Zamanlayıcı çalışıyor: Evet", buffer.getvalue())

    @patch("lksu.cli.core.config", return_value={**CFG, "report_language": "en"})
    @patch("lksu.cli.core.run")
    def test_active_json_keeps_machine_keys(self, run, config):
        from types import SimpleNamespace
        run.side_effect = [
            SimpleNamespace(returncode=0, stdout="inactive\\n"),
            SimpleNamespace(returncode=1, stdout="disabled\\n"),
        ]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(cli.main(["active", "--json"]), 0)
        data = __import__("json").loads(buffer.getvalue())
        self.assertFalse(data["timer_active"])
        self.assertFalse(data["timer_enabled"])

    def test_version_flag_exits_without_config_or_kernel_operations(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), self.assertRaises(SystemExit) as raised:
            cli.main(["--version"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("LKSU ", buffer.getvalue())
