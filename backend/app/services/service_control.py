from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR
from app.core.exceptions import AppException, ErrorCode, NotFoundError


REPO_ROOT = BASE_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import manage_services  # noqa: E402


SERVICE_LOG_DIR = REPO_ROOT / ".runtime" / "service-logs"
CONTROLLED_SERVICES = {"wechat_exporter", "mediacrawler_xhs"}
TASK_TTL_SECONDS = 20 * 60


@dataclass
class ServiceActionTask:
    task_id: str
    service_name: str
    action: str
    status: str = "queued"
    progress: int = 0
    message: str = "已进入队列。"
    service_online: bool = False
    service_status: str = "unknown"
    error: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0


_TASKS: dict[str, ServiceActionTask] = {}
_ACTIVE_TASKS: dict[str, str] = {}
_TASKS_LOCK = threading.Lock()
_SERVICE_LOCKS = {name: threading.Lock() for name in CONTROLLED_SERVICES}


def _cleanup_tasks(now: float | None = None) -> None:
    current = time.time() if now is None else now
    expired = [
        task_id
        for task_id, task in _TASKS.items()
        if task.status in {"success", "failed"} and (current - task.updated_at) > TASK_TTL_SECONDS
    ]
    for task_id in expired:
        task = _TASKS.pop(task_id, None)
        if task and _ACTIVE_TASKS.get(task.service_name) == task_id:
            _ACTIVE_TASKS.pop(task.service_name, None)


def _serialize_task(task: ServiceActionTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "service_name": task.service_name,
        "action": task.action,
        "status": task.status,
        "progress": task.progress,
        "message": task.message,
        "service_online": task.service_online,
        "service_status": task.service_status,
        "error": task.error,
    }


def _update_task(
    task: ServiceActionTask,
    *,
    status: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    service_online: bool | None = None,
    service_status: str | None = None,
    error: str | None = None,
) -> None:
    with _TASKS_LOCK:
        if status is not None:
            task.status = status
        if progress is not None:
            task.progress = max(0, min(int(progress), 100))
        if message is not None:
            task.message = message
        if service_online is not None:
            task.service_online = service_online
        if service_status is not None:
            task.service_status = service_status
        task.error = error
        task.updated_at = time.time()


def _service_context(service_name: str) -> tuple[dict[str, Any], Path, dict[str, str]]:
    services, global_env, overrides = manage_services.load_manifest()
    service_map = {str(service["name"]): service for service in services}
    service = service_map.get(service_name)
    if service is None:
        raise NotFoundError(f"Managed service '{service_name}' not found", "ManagedService")
    if service_name not in CONTROLLED_SERVICES:
        raise AppException(
            f"Managed service '{service_name}' is not available for console control",
            ErrorCode.FORBIDDEN,
            403,
            {"service_name": service_name},
        )

    cwd, env = manage_services.prepare_service(
        service,
        global_env,
        overrides,
        update=False,
        skip_install=True,
    )
    return service, cwd, env


def _service_log_path(service_name: str) -> Path:
    SERVICE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    return SERVICE_LOG_DIR / f"{service_name}.log"


def _tail_log(log_path: Path, *, lines: int = 20) -> str:
    if not log_path.exists():
        return ""
    content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def _launch_service(service: dict[str, Any], cwd: Path, env: dict[str, str]) -> tuple[subprocess.Popen[bytes], Path]:
    command = manage_services.resolve_command(service["start"])
    log_path = _service_log_path(str(service["name"]))
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    with log_path.open("ab") as stream:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
    return process, log_path


def _wait_until_stopped(
    service: dict[str, Any],
    task: ServiceActionTask,
    *,
    start_progress: int = 35,
    end_progress: int = 65,
    timeout_seconds: int = 15,
) -> None:
    ready_port = service.get("ready_port")
    if not ready_port:
        raise AppException(
            f"Managed service '{service['name']}' does not expose a controllable port",
            ErrorCode.INVALID_REQUEST,
            400,
            {"service_name": service["name"]},
        )

    deadline = time.time() + timeout_seconds
    started_at = time.time()
    while time.time() < deadline:
        if not manage_services.is_port_in_use(int(ready_port)):
            return
        ratio = min((time.time() - started_at) / timeout_seconds, 1)
        progress = start_progress + int((end_progress - start_progress) * ratio)
        _update_task(task, progress=progress, message="正在等待旧进程完全退出...", service_online=True, service_status="stopping")
        time.sleep(1)

    raise AppException(
        f"Service on port {ready_port} did not stop within {timeout_seconds}s",
        ErrorCode.TIMEOUT_ERROR,
        504,
        {"port": ready_port, "timeout_seconds": timeout_seconds},
    )


def _stop_service_if_running(service: dict[str, Any], task: ServiceActionTask) -> bool:
    ready_port = service.get("ready_port")
    if not ready_port:
        raise AppException(
            f"Managed service '{service['name']}' does not expose a controllable port",
            ErrorCode.INVALID_REQUEST,
            400,
            {"service_name": service["name"]},
        )

    pids = manage_services.pids_for_port(int(ready_port))
    if not pids:
        return False

    _update_task(task, progress=30, message="正在停止当前服务实例...", service_online=True, service_status="stopping")
    for pid in pids:
        manage_services.stop_pid(pid)
    _wait_until_stopped(service, task)
    return True


def _wait_for_ready(
    service: dict[str, Any],
    process: subprocess.Popen[bytes],
    log_path: Path,
    task: ServiceActionTask,
    *,
    start_progress: int = 72,
    end_progress: int = 96,
    timeout_seconds: int = 90,
) -> None:
    deadline = time.time() + timeout_seconds
    started_at = time.time()
    while time.time() < deadline:
        if manage_services.service_is_healthy(service):
            return
        exit_code = process.poll()
        if exit_code is not None:
            raise AppException(
                f"{service['name']} exited before becoming ready",
                ErrorCode.INTERNAL_ERROR,
                500,
                {
                    "service_name": service["name"],
                    "exit_code": exit_code,
                    "log_tail": _tail_log(log_path),
                },
            )
        ratio = min((time.time() - started_at) / timeout_seconds, 1)
        progress = start_progress + int((end_progress - start_progress) * ratio)
        _update_task(task, progress=progress, message="正在执行健康检查...", service_online=False, service_status="starting")
        time.sleep(1)

    raise AppException(
        f"{service['name']} did not become ready within {timeout_seconds}s",
        ErrorCode.TIMEOUT_ERROR,
        504,
        {
            "service_name": service["name"],
            "timeout_seconds": timeout_seconds,
            "log_tail": _tail_log(log_path),
        },
    )


def _run_service_action(task: ServiceActionTask) -> None:
    lock = _SERVICE_LOCKS[task.service_name]
    try:
        with lock:
            _update_task(task, status="running", progress=8, message="正在加载服务配置...", service_status="preparing")
            service, cwd, env = _service_context(task.service_name)
            already_running = manage_services.service_is_healthy(service)

            if task.action == "start" and already_running:
                _update_task(
                    task,
                    status="success",
                    progress=100,
                    message="服务已在运行。",
                    service_online=True,
                    service_status="online",
                )
                return

            if task.action == "stop":
                if not already_running:
                    _update_task(
                        task,
                        status="success",
                        progress=100,
                        message="服务当前未运行。",
                        service_online=False,
                        service_status="offline",
                    )
                    return
                _stop_service_if_running(service, task)
                _update_task(
                    task,
                    status="success",
                    progress=100,
                    message="服务已停止。",
                    service_online=False,
                    service_status="offline",
                )
                return

            if task.action == "restart":
                restarted = _stop_service_if_running(service, task)
                _update_task(
                    task,
                    progress=68,
                    message="正在拉起新的服务实例...",
                    service_online=False,
                    service_status="starting",
                )
            else:
                restarted = False
                _update_task(
                    task,
                    progress=25,
                    message="正在准备启动环境...",
                    service_online=False,
                    service_status="starting",
                )

            process, log_path = _launch_service(service, cwd, env)
            _update_task(task, progress=72, message="服务已拉起，等待健康检查...", service_online=False, service_status="starting")
            _wait_for_ready(service, process, log_path, task)
            _update_task(
                task,
                status="success",
                progress=100,
                message="服务已重启。" if task.action == "restart" and restarted else "服务已启动。",
                service_online=True,
                service_status="online",
            )
    except AppException as exc:
        details = exc.details or {}
        error = details.get("log_tail") or exc.message
        _update_task(
            task,
            status="failed",
            progress=100,
            message=exc.message,
            service_online=False,
            service_status="error",
            error=str(error),
        )
    except Exception as exc:  # pragma: no cover - defensive fallback
        _update_task(
            task,
            status="failed",
            progress=100,
            message="服务控制失败。",
            service_online=False,
            service_status="error",
            error=str(exc),
        )
    finally:
        with _TASKS_LOCK:
            if _ACTIVE_TASKS.get(task.service_name) == task.task_id and task.status in {"success", "failed"}:
                _ACTIVE_TASKS.pop(task.service_name, None)


def start_service_action(service_name: str, action: str) -> dict[str, Any]:
    action_name = str(action or "").strip().lower()
    if action_name not in {"start", "stop", "restart"}:
        raise AppException(
            f"Unsupported service action '{action}'",
            ErrorCode.INVALID_REQUEST,
            400,
            {"service_name": service_name, "action": action},
        )

    if service_name not in CONTROLLED_SERVICES:
        raise NotFoundError(f"Managed service '{service_name}' not found", "ManagedService")

    with _TASKS_LOCK:
        _cleanup_tasks()
        active_task_id = _ACTIVE_TASKS.get(service_name)
        if active_task_id:
            active_task = _TASKS.get(active_task_id)
            if active_task and active_task.status in {"queued", "running"}:
                return _serialize_task(active_task)

        created_at = time.time()
        task = ServiceActionTask(
            task_id=uuid.uuid4().hex,
            service_name=service_name,
            action=action_name,
            status="queued",
            progress=0,
            message="已进入队列。",
            service_online=False,
            service_status="queued",
            created_at=created_at,
            updated_at=created_at,
        )
        _TASKS[task.task_id] = task
        _ACTIVE_TASKS[service_name] = task.task_id

    threading.Thread(target=_run_service_action, args=(task,), daemon=True).start()
    return _serialize_task(task)


def get_service_action(task_id: str) -> dict[str, Any]:
    with _TASKS_LOCK:
        _cleanup_tasks()
        task = _TASKS.get(task_id)
        if task is None:
            raise NotFoundError("Service action task not found", "ManagedServiceAction")
        return _serialize_task(task)

