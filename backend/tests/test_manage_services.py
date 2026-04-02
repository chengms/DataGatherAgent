import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

import manage_services  # noqa: E402


class ManageServicesTests(unittest.TestCase):
    def test_missing_required_env_raises_clear_error(self) -> None:
        service = {"name": "wechat_exporter", "required_env": ["WECHAT_EXPORTER_API_KEY"]}
        with self.assertRaises(RuntimeError) as context:
            manage_services.ensure_required_env(service, {})
        self.assertIn("services.local.example.json", str(context.exception))

    def test_missing_required_binary_raises_error(self) -> None:
        service = {"name": "backend", "requires": ["python", "missing-tool"]}
        with patch("manage_services.shutil.which") as which:
            which.side_effect = lambda name: None if name == "missing-tool" else "/usr/bin/python"
            with self.assertRaises(RuntimeError) as context:
                manage_services.ensure_required_binaries(service)
        self.assertIn("missing-tool", str(context.exception))

    def test_port_check_detects_busy_port(self) -> None:
        with patch("manage_services.socket.socket") as socket_cls:
            socket_instance = socket_cls.return_value.__enter__.return_value
            socket_instance.connect_ex.return_value = 0
            self.assertTrue(manage_services.is_port_in_use(8000))

    def test_prepare_service_runs_multiple_install_steps(self) -> None:
        service = {
            "name": "mediacrawler_xhs",
            "kind": "internal",
            "cwd": ".",
            "install": [["uv", "sync"], ["uv", "run", "playwright", "install"]],
        }
        with patch("manage_services.ensure_required_binaries"), patch(
            "manage_services.ensure_required_env"
        ), patch("manage_services.run_command") as run_command:
            manage_services.prepare_service(service, {}, {}, update=False, skip_install=False)
        self.assertEqual(run_command.call_count, 2)
        self.assertEqual(run_command.call_args_list[0].args[0], ["uv", "sync"])
        self.assertEqual(run_command.call_args_list[1].args[0], ["uv", "run", "playwright", "install"])

    def test_prepare_service_can_skip_install(self) -> None:
        service = {"name": "backend", "kind": "internal", "cwd": ".", "install": ["python", "-m", "pip", "install", "-e", "."]}
        with patch("manage_services.ensure_required_binaries"), patch(
            "manage_services.ensure_required_env"
        ), patch("manage_services.run_command") as run_command:
            manage_services.prepare_service(service, {}, {}, update=False, skip_install=True)
        run_command.assert_not_called()

    def test_run_login_check_reads_command_json_payload(self) -> None:
        service = {
            "name": "wechat_exporter",
            "login_check": {
                "type": "command_json",
                "argv": ["python", "scripts/wechat_login_status.py"],
                "cwd": ".",
                "ok_field": "ok",
                "ok_equals": True,
            },
        }
        completed = type("Completed", (), {"stdout": '{"ok": true, "reason": "ok"}', "stderr": "", "returncode": 0})()
        with patch("manage_services.subprocess.run", return_value=completed):
            ok, reason = manage_services.run_login_check(service, {})
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_command_stop_uses_ready_ports(self) -> None:
        services = [
            {"name": "wechat_exporter", "ready_port": 3000},
            {"name": "backend", "ready_port": 8000},
        ]
        with patch("manage_services.load_manifest", return_value=(services, {}, {})), patch(
            "manage_services.pids_for_port"
        ) as pids_for_port, patch("manage_services.stop_pid") as stop_pid:
            pids_for_port.side_effect = [[111], []]
            manage_services.command_stop()
        stop_pid.assert_called_once_with(111)


if __name__ == "__main__":
    unittest.main()
