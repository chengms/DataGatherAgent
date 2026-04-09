import sys
import tempfile
import unittest
from io import BytesIO, StringIO
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
        self.assertEqual(run_command.call_count, 3)
        self.assertEqual(run_command.call_args_list[0].args[0], ["uv", "sync"])
        self.assertEqual(run_command.call_args_list[1].args[0], ["uv", "run", "playwright", "install"])
        self.assertEqual(run_command.call_args_list[2].args[0][1], "scripts/ensure_mediacrawler_xhs_dependency.py")

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

    def test_cleanup_stale_git_lock_removes_old_lock_without_git_process(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_dir = Path(tempdir)
            git_dir = repo_dir / ".git"
            git_dir.mkdir()
            lock_path = git_dir / "index.lock"
            lock_path.write_text("locked", encoding="utf-8")
            with patch("manage_services.git_process_running", return_value=False), patch(
                "manage_services.time.time", return_value=lock_path.stat().st_mtime + 120
            ):
                manage_services.cleanup_stale_git_lock(repo_dir)
            self.assertFalse(lock_path.exists())

    def test_spawn_service_uses_utf8_decoding_for_child_output(self) -> None:
        service = {"name": "wechat_exporter", "start": ["node", "server.js"]}
        with patch("manage_services.resolve_command", return_value=["node", "server.js"]), patch(
            "manage_services.subprocess.Popen"
        ) as popen, patch("manage_services.threading.Thread") as thread_cls:
            manage_services.spawn_service(service, Path("."), {})
        kwargs = popen.call_args.kwargs
        self.assertTrue(kwargs["text"])
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "replace")
        self.assertEqual(thread_cls.call_count, 2)

    def test_write_console_line_falls_back_when_stdout_cannot_encode(self) -> None:
        class FailingStdout(StringIO):
            encoding = "gbk"

            def write(self, value: str) -> int:
                raise UnicodeEncodeError("gbk", value, 0, 1, "illegal multibyte sequence")

            @property
            def buffer(self):
                return self._buffer

        stdout = FailingStdout()
        stdout._buffer = BytesIO()
        with patch("manage_services.sys.stdout", stdout):
            manage_services._write_console_line("▀ unicode block")
        self.assertIn(b"? unicode block", stdout._buffer.getvalue())

    def test_start_prepared_services_reuses_existing_port_listener(self) -> None:
        service = {"name": "wechat_exporter", "ready_port": 3000}
        prepared = [(service, Path("."), {})]
        with patch("manage_services.is_port_in_use", return_value=True), patch(
            "manage_services.ensure_service_ready"
        ) as ensure_service_ready, patch("manage_services.spawn_service") as spawn_service, patch(
            "manage_services.time.sleep", side_effect=KeyboardInterrupt
        ):
            manage_services.start_prepared_services(prepared)
        ensure_service_ready.assert_called_once_with(service)
        spawn_service.assert_not_called()

    def test_command_up_reuses_healthy_service_and_skips_prepare(self) -> None:
        service = {"name": "backend", "kind": "internal", "cwd": "backend", "ready_port": 8000}
        with patch("manage_services.load_manifest", return_value=([service], {}, {})), patch(
            "manage_services.service_is_healthy", return_value=True
        ), patch(
            "manage_services.resolve_service_cwd", return_value=Path("backend")
        ), patch(
            "manage_services.merged_env", return_value={"PYTHONUNBUFFERED": "1"}
        ), patch(
            "manage_services.ensure_required_env"
        ) as ensure_required_env, patch(
            "manage_services.prepare_service"
        ) as prepare_service, patch(
            "manage_services.start_prepared_services"
        ) as start_prepared_services:
            manage_services.command_up(update=True, skip_install=False)
        ensure_required_env.assert_called_once_with(service, {"PYTHONUNBUFFERED": "1"})
        prepare_service.assert_not_called()
        start_prepared_services.assert_called_once()

    def test_refresh_update_status_records_available_updates(self) -> None:
        service = {"name": "wechat_exporter", "kind": "managed_repo", "repo_dir": "external_tools/wechat-article-exporter"}
        with patch("manage_services.inspect_repo_update", return_value={"service_name": "wechat_exporter", "status": "update_available", "ahead_by": 2, "summary": "origin/master is ahead by 2 commit(s)"}), patch(
            "manage_services.write_update_status"
        ) as write_update_status:
            payload = manage_services.refresh_update_status([service])
        self.assertEqual(payload["items"][0]["status"], "update_available")
        write_update_status.assert_called_once_with(payload)


if __name__ == "__main__":
    unittest.main()
