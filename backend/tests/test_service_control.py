import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import service_control


class ServiceControlTests(unittest.TestCase):
    def setUp(self) -> None:
        service_control._TASKS.clear()
        service_control._ACTIVE_TASKS.clear()

    def tearDown(self) -> None:
        service_control._TASKS.clear()
        service_control._ACTIVE_TASKS.clear()

    def test_start_service_action_reuses_active_task(self) -> None:
        task = service_control.ServiceActionTask(
            task_id="existing-task",
            service_name="wechat_exporter",
            action="start",
            status="running",
            progress=48,
            message="正在执行健康检查...",
            created_at=1.0,
            updated_at=1.0,
        )
        service_control._TASKS[task.task_id] = task
        service_control._ACTIVE_TASKS[task.service_name] = task.task_id

        payload = service_control.start_service_action("wechat_exporter", "restart")

        self.assertEqual(payload["task_id"], "existing-task")
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["progress"], 48)

    def test_run_service_action_marks_start_as_success_when_already_running(self) -> None:
        task = service_control.ServiceActionTask(
            task_id="task-1",
            service_name="wechat_exporter",
            action="start",
            created_at=1.0,
            updated_at=1.0,
        )
        service = {"name": "wechat_exporter", "ready_port": 3000}
        with patch("app.services.service_control._service_context", return_value=(service, Path("."), {})), patch(
            "app.services.service_control.manage_services.service_is_healthy", return_value=True
        ):
            service_control._run_service_action(task)

        self.assertEqual(task.status, "success")
        self.assertEqual(task.progress, 100)
        self.assertTrue(task.service_online)
        self.assertEqual(task.service_status, "online")

    def test_run_service_action_marks_stop_as_success_when_not_running(self) -> None:
        task = service_control.ServiceActionTask(
            task_id="task-2",
            service_name="wechat_exporter",
            action="stop",
            created_at=1.0,
            updated_at=1.0,
        )
        service = {"name": "wechat_exporter", "ready_port": 3000}
        with patch("app.services.service_control._service_context", return_value=(service, Path("."), {})), patch(
            "app.services.service_control.manage_services.service_is_healthy", return_value=False
        ):
            service_control._run_service_action(task)

        self.assertEqual(task.status, "success")
        self.assertEqual(task.progress, 100)
        self.assertFalse(task.service_online)
        self.assertEqual(task.service_status, "offline")

    def test_run_service_action_starts_service_after_restart(self) -> None:
        task = service_control.ServiceActionTask(
            task_id="task-3",
            service_name="mediacrawler_xhs",
            action="restart",
            created_at=1.0,
            updated_at=1.0,
        )
        service = {"name": "mediacrawler_xhs", "ready_port": 8080}
        process = object()
        with patch("app.services.service_control._service_context", return_value=(service, Path("."), {})), patch(
            "app.services.service_control.manage_services.service_is_healthy", return_value=True
        ), patch(
            "app.services.service_control._stop_service_if_running", return_value=True
        ), patch(
            "app.services.service_control._launch_service", return_value=(process, Path("mediacrawler_xhs.log"))
        ), patch("app.services.service_control._wait_for_ready"):
            service_control._run_service_action(task)

        self.assertEqual(task.status, "success")
        self.assertEqual(task.progress, 100)
        self.assertTrue(task.service_online)
        self.assertEqual(task.service_status, "online")


if __name__ == "__main__":
    unittest.main()
