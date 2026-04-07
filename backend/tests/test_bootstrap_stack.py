import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

import bootstrap_stack  # noqa: E402


class BootstrapStackTests(unittest.TestCase):
    def test_print_preflight_report_emits_sections(self) -> None:
        report = {
            "services": [{"name": "backend", "status": "prepared", "detail": "internal @ backend"}],
            "checks": [{"name": "wechat login", "status": "ok", "detail": "existing login is still valid"}],
            "startup": [{"name": "next step", "status": "ready", "detail": "starting managed services"}],
        }
        with patch("bootstrap_stack.manage_services.log") as log:
            bootstrap_stack.print_preflight_report(report)
        rendered = "\n".join(call.args[0] for call in log.call_args_list)
        self.assertIn("启动前自检摘要", rendered)
        self.assertIn("服务准备", rendered)
        self.assertIn("backend:", rendered)
        self.assertIn("wechat login: 正常", rendered)
        self.assertIn("next step: 即将启动", rendered)

    def test_install_service_without_env_gate_reuses_healthy_service(self) -> None:
        report = {"services": [], "checks": [], "startup": []}
        service = {"name": "backend", "kind": "internal", "cwd": "backend"}
        with patch("bootstrap_stack.manage_services.ensure_required_binaries"), patch(
            "bootstrap_stack.manage_services.service_is_healthy", return_value=True
        ), patch(
            "bootstrap_stack.manage_services.resolve_service_cwd", return_value=Path("backend")
        ), patch(
            "bootstrap_stack.manage_services.merged_env", return_value={"PYTHONUNBUFFERED": "1"}
        ), patch(
            "bootstrap_stack.manage_services.ensure_required_env"
        ) as ensure_required_env, patch(
            "bootstrap_stack.manage_services.run_command"
        ) as run_command:
            cwd, env = bootstrap_stack.install_service_without_env_gate(
                service,
                {},
                {},
                update=True,
                skip_install=False,
                report=report,
            )
        self.assertEqual(cwd, Path("backend"))
        self.assertEqual(env, {"PYTHONUNBUFFERED": "1"})
        ensure_required_env.assert_called_once_with(service, {"PYTHONUNBUFFERED": "1"})
        run_command.assert_not_called()
        self.assertEqual(report["services"][0]["status"], "reused")

    def test_ensure_wechat_login_keeps_valid_session(self) -> None:
        process = object()
        with patch("bootstrap_stack.service_is_already_running", return_value=False), patch(
            "bootstrap_stack.start_service_temp", return_value=process
        ), patch(
            "bootstrap_stack.run_json_script", return_value={"ok": True, "reason": "ok"}
        ), patch("bootstrap_stack.run_login_script") as run_login_script:
            result = bootstrap_stack.ensure_wechat_login({"name": "wechat_exporter"}, Path("."), {})
        self.assertIs(result, process)
        run_login_script.assert_not_called()

    def test_ensure_wechat_login_records_report_entry(self) -> None:
        process = object()
        report = {"services": [], "checks": [], "startup": []}
        with patch("bootstrap_stack.service_is_already_running", return_value=False), patch(
            "bootstrap_stack.start_service_temp", return_value=process
        ), patch(
            "bootstrap_stack.run_json_script", return_value={"ok": True, "reason": "ok"}
        ):
            bootstrap_stack.ensure_wechat_login({"name": "wechat_exporter"}, Path("."), {}, report=report)
        self.assertEqual(report["checks"][0]["name"], "wechat login")
        self.assertEqual(report["checks"][0]["status"], "ok")

    def test_ensure_wechat_login_refreshes_invalid_session_in_interactive_mode(self) -> None:
        process = object()
        with patch("bootstrap_stack.service_is_already_running", return_value=False), patch(
            "bootstrap_stack.start_service_temp", return_value=process
        ), patch(
            "bootstrap_stack.run_json_script",
            side_effect=[{"ok": False, "reason": "auth_invalid"}, {"ok": True, "reason": "ok"}],
        ), patch("bootstrap_stack.run_login_script") as run_login_script:
            result = bootstrap_stack.ensure_wechat_login(
                {"name": "wechat_exporter"},
                Path("."),
                {},
                interactive_refresh=True,
            )
        self.assertIs(result, process)
        run_login_script.assert_called_once_with("wechat_terminal_login.py")

    def test_ensure_wechat_login_defers_manual_refresh_by_default(self) -> None:
        process = object()
        report = {"services": [], "checks": [], "startup": []}
        with patch("bootstrap_stack.service_is_already_running", return_value=False), patch(
            "bootstrap_stack.start_service_temp", return_value=process
        ), patch(
            "bootstrap_stack.run_json_script", return_value={"ok": False, "reason": "auth_invalid"}
        ), patch("bootstrap_stack.run_login_script") as run_login_script:
            result = bootstrap_stack.ensure_wechat_login(
                {"name": "wechat_exporter"},
                Path("."),
                {},
                report=report,
            )
        self.assertIs(result, process)
        run_login_script.assert_not_called()
        self.assertEqual(report["checks"][0]["status"], "skipped")
        self.assertIn("web console", report["checks"][0]["detail"])

    def test_ensure_wechat_login_reuses_existing_service(self) -> None:
        with patch("bootstrap_stack.service_is_already_running", return_value=True), patch(
            "bootstrap_stack.start_service_temp"
        ) as start_service_temp, patch(
            "bootstrap_stack.run_json_script", return_value={"ok": True, "reason": "ok"}
        ):
            result = bootstrap_stack.ensure_wechat_login({"name": "wechat_exporter"}, Path("."), {})
        self.assertIsNone(result)
        start_service_temp.assert_not_called()

    def test_ensure_mediacrawler_platform_login_refreshes_invalid_session(self) -> None:
        with patch(
            "bootstrap_stack.run_json_script",
            side_effect=[{"ok": False, "reason": "xhs:cookie_invalid"}, {"ok": True, "reason": "ok"}],
        ), patch("bootstrap_stack.run_login_script") as run_login_script:
            bootstrap_stack.ensure_mediacrawler_platform_login("xhs")
        run_login_script.assert_called_once_with("mediacrawler_terminal_login.py", "--platform", "xhs")


if __name__ == "__main__":
    unittest.main()
