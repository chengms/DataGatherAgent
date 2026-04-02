#!/usr/bin/env python3
"""Manage local services and clean external repository checkouts."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT_DIR / "services.manifest.json"
LOCAL_OVERRIDE_PATH = ROOT_DIR / "services.local.json"


def log(message: str) -> None:
    print(f"[services] {message}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage local backend and external crawler services.")
    parser.add_argument(
        "command",
        choices=["up", "ensure-repos", "update-repos"],
        nargs="?",
        default="up",
    )
    parser.add_argument("--no-update", action="store_true", help="Skip pulling updates for clean managed repos.")
    parser.add_argument("--skip-install", action="store_true", help="Skip install steps and only prepare/start services.")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_manifest() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    manifest = load_json(MANIFEST_PATH)
    overrides = load_json(LOCAL_OVERRIDE_PATH) if LOCAL_OVERRIDE_PATH.exists() else {}
    global_env = overrides.get("global_env", {})
    service_overrides = overrides.get("services", {})
    return manifest["services"], global_env, service_overrides


def resolve_path(value: str) -> Path:
    return (ROOT_DIR / value).resolve()


def merged_env(service: dict[str, Any], global_env: dict[str, Any], service_overrides: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    env.update({str(k): str(v) for k, v in global_env.items()})
    env.update({str(k): str(v) for k, v in service.get("env", {}).items()})
    override_env = service_overrides.get(service["name"], {}).get("env", {})
    env.update({str(k): str(v) for k, v in override_env.items()})
    if service["name"] == "backend":
        env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def ensure_required_binaries(service: dict[str, Any]) -> None:
    missing: list[str] = []
    for binary in service.get("requires", []):
        if shutil.which(binary) is None:
            missing.append(binary)
    if missing:
        raise RuntimeError(
            f"{service['name']} is missing required commands: {', '.join(missing)}"
        )


def ensure_required_env(service: dict[str, Any], env: dict[str, str]) -> None:
    missing: list[str] = []
    for name in service.get("required_env", []):
        value = env.get(name)
        if value in {None, ""}:
            missing.append(name)
    if missing:
        config_hint = (
            "Copy services.local.example.json to services.local.json and fill in the missing values, "
            "or export them in the current shell environment."
        )
        raise RuntimeError(
            f"{service['name']} is missing required environment values: {', '.join(missing)}. "
            + config_hint
        )


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def resolve_command(command: list[str]) -> list[str]:
    if not command:
        return command

    executable = command[0]
    resolved = shutil.which(executable)
    if resolved:
        resolved_path = Path(resolved)
        if os.name == "nt" and resolved_path.suffix.lower() == "":
            for suffix in (".cmd", ".exe", ".bat"):
                candidate = Path(f"{resolved}{suffix}")
                if candidate.exists():
                    command = [str(candidate), *command[1:]]
                    break
            else:
                command = [resolved, *command[1:]]
        else:
            command = [resolved, *command[1:]]
    return command


def run_command(command: list[str], cwd: Path, env: dict[str, str]) -> None:
    command = resolve_command(command)
    log(f"running {shlex.join(command)} in {cwd}")
    completed = subprocess.run(command, cwd=cwd, env=env, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed with exit code {completed.returncode}: {shlex.join(command)}")


def git_output(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def normalize_status_path(raw_path: str) -> str:
    path = raw_path.strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.strip().strip('"').replace("\\", "/")


def is_generated_path(service: dict[str, Any], status_path: str) -> bool:
    for rel_path in service.get("generated_paths", []):
        normalized = str(Path(rel_path).as_posix()).rstrip("/")
        if status_path == normalized or status_path.startswith(f"{normalized}/"):
            return True
    return False


def filter_generated_status(service: dict[str, Any], status: str) -> str:
    kept_lines: list[str] = []
    for line in status.splitlines():
        if len(line) < 4:
            kept_lines.append(line)
            continue
        status_path = normalize_status_path(line[3:])
        if is_generated_path(service, status_path):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines).strip()


def cleanup_generated_paths(service: dict[str, Any], repo_dir: Path) -> None:
    for rel_path in service.get("generated_paths", []):
        target = (repo_dir / rel_path).resolve()
        try:
            target.relative_to(repo_dir.resolve())
        except ValueError as exc:
            raise RuntimeError(f"generated path escapes managed repository: {target}") from exc
        if not target.exists():
            continue
        try:
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=False)
            else:
                target.unlink()
        except OSError as exc:
            log(f"skipping cleanup for locked generated path {target}: {exc}")


def ensure_managed_repo(service: dict[str, Any], update: bool) -> Path:
    repo_dir = resolve_path(service["repo_dir"])
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    branch = service.get("branch", "main")
    repo_url = service["repo_url"]

    if not repo_dir.exists():
        log(f"cloning {repo_url} into {repo_dir}")
        run_command(["git", "clone", "--branch", branch, repo_url, str(repo_dir)], ROOT_DIR, os.environ.copy())
        return repo_dir

    if not (repo_dir / ".git").exists():
        raise RuntimeError(f"{repo_dir} exists but is not a git repository")

    cleanup_generated_paths(service, repo_dir)

    status = filter_generated_status(service, git_output(["status", "--porcelain"], repo_dir))
    if status:
        raise RuntimeError(
            f"managed repository {repo_dir} is dirty; commit/stash/revert changes there before running updates"
        )

    if update:
        log(f"updating {repo_dir.name} with ff-only pull")
        run_command(["git", "fetch", "origin", branch], repo_dir, os.environ.copy())
        run_command(["git", "pull", "--ff-only", "origin", branch], repo_dir, os.environ.copy())

    return repo_dir


def stream_output(pipe, prefix: str) -> None:
    try:
        for line in iter(pipe.readline, ""):
            if not line:
                break
            print(f"[{prefix}] {line.rstrip()}", flush=True)
    finally:
        pipe.close()


def spawn_service(service: dict[str, Any], cwd: Path, env: dict[str, str]) -> subprocess.Popen[str]:
    command = resolve_command(service["start"])
    log(f"starting {service['name']}: {shlex.join(command)}")
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    threading.Thread(target=stream_output, args=(process.stdout, service["name"]), daemon=True).start()
    threading.Thread(target=stream_output, args=(process.stderr, service["name"]), daemon=True).start()
    return process


def ensure_service_ready(service: dict[str, Any]) -> None:
    ready_port = service.get("ready_port")
    if ready_port:
        wait_for_port(int(ready_port))
        log(f"{service['name']} is ready on port {ready_port}")
    healthcheck_url = service.get("healthcheck_url")
    if healthcheck_url:
        wait_for_healthcheck(str(healthcheck_url))
        log(f"{service['name']} passed healthcheck {healthcheck_url}")


def wait_for_port(port: int, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(1)
    raise RuntimeError(f"service on port {port} did not become ready within {timeout_seconds}s")


def wait_for_healthcheck(url: str, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if 200 <= response.status < 300:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(1)
            continue
        time.sleep(1)
    raise RuntimeError(f"service healthcheck did not succeed within {timeout_seconds}s: {url}")


def prepare_service(
    service: dict[str, Any],
    global_env: dict[str, Any],
    overrides: dict[str, Any],
    update: bool,
    *,
    skip_install: bool,
) -> tuple[Path, dict[str, str]]:
    ensure_required_binaries(service)
    if service["kind"] == "managed_repo":
        cwd = ensure_managed_repo(service, update=update)
    else:
        cwd = resolve_path(service["cwd"])
    env = merged_env(service, global_env, overrides)
    ensure_required_env(service, env)
    install_command = service.get("install")
    if install_command and not skip_install:
        if install_command and isinstance(install_command[0], list):
            for step in install_command:
                run_command(step, cwd, env)
        else:
            run_command(install_command, cwd, env)
    return cwd, env


def command_ensure_repos(update: bool, *, skip_install: bool) -> None:
    services, global_env, overrides = load_manifest()
    for service in services:
        if service["kind"] == "managed_repo":
            prepare_service(service, global_env, overrides, update=update, skip_install=skip_install)
    log("managed repositories are ready")


def command_up(update: bool, *, skip_install: bool) -> None:
    services, global_env, overrides = load_manifest()
    prepared: list[tuple[dict[str, Any], Path, dict[str, str]]] = []
    for service in services:
        ready_port = service.get("ready_port")
        if ready_port and is_port_in_use(int(ready_port)):
            raise RuntimeError(
                f"{service['name']} cannot start because port {ready_port} is already in use"
            )
        cwd, env = prepare_service(service, global_env, overrides, update=update, skip_install=skip_install)
        prepared.append((service, cwd, env))

    start_prepared_services(prepared)


def start_prepared_services(
    prepared: list[tuple[dict[str, Any], Path, dict[str, str]]],
    *,
    existing_processes: list[tuple[dict[str, Any], subprocess.Popen[str]]] | None = None,
) -> None:
    processes: list[tuple[dict[str, Any], subprocess.Popen[str]]] = list(existing_processes or [])
    started_names = {service["name"] for service, _ in processes}
    try:
        for service, cwd, env in prepared:
            if service["name"] in started_names:
                ensure_service_ready(service)
                continue
            process = spawn_service(service, cwd, env)
            processes.append((service, process))
            ensure_service_ready(service)

        log("all services are running; press Ctrl+C to stop them")
        while True:
            for service, process in processes:
                exit_code = process.poll()
                if exit_code is not None:
                    raise RuntimeError(f"{service['name']} exited unexpectedly with code {exit_code}")
            time.sleep(1)
    except KeyboardInterrupt:
        log("stopping services")
    finally:
        for service, process in reversed(processes):
            if process.poll() is None:
                process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM)
        for service, process in reversed(processes):
            if process.poll() is None:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "ensure-repos":
            command_ensure_repos(update=not args.no_update, skip_install=args.skip_install)
        elif args.command == "update-repos":
            command_ensure_repos(update=True, skip_install=args.skip_install)
        else:
            command_up(update=not args.no_update, skip_install=args.skip_install)
    except Exception as exc:
        log(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
