#!/usr/bin/env python3
"""Single-entry bootstrap for environment scan, install, QR login, and full stack startup."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

import manage_services
import service_env_store


ROOT_DIR = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap the full stack: scan environment, install deps, run QR logins, then start all services."
    )
    parser.add_argument("--no-update", action="store_true", help="Skip pulling updates for clean managed repositories.")
    parser.add_argument("--skip-install", action="store_true", help="Skip dependency installation and only prepare/start services.")
    parser.add_argument("--skip-wechat-login", action="store_true", help="Skip the WeChat QR login step.")
    parser.add_argument("--skip-xhs-login", action="store_true", help="Skip the Xiaohongshu QR login step.")
    return parser.parse_args()


def load_manifest_map() -> tuple[dict[str, dict], dict[str, str], dict[str, dict]]:
    services, global_env, overrides = manage_services.load_manifest()
    return {service["name"]: service for service in services}, global_env, overrides


def ensure_local_config_exists() -> None:
    if service_env_store.LOCAL_OVERRIDE_PATH.exists():
        return
    payload = service_env_store.load_local_config()
    service_env_store.save_local_config(payload)


def install_service_without_env_gate(
    service: dict,
    global_env: dict[str, str],
    overrides: dict[str, dict],
    *,
    update: bool,
    skip_install: bool,
) -> tuple[Path, dict[str, str]]:
    manage_services.ensure_required_binaries(service)
    if service["kind"] == "managed_repo":
        cwd = manage_services.ensure_managed_repo(service, update=update)
    else:
        cwd = manage_services.resolve_path(service["cwd"])
    env = manage_services.merged_env(service, global_env, overrides)
    install_command = service.get("install")
    if install_command and not skip_install:
        if install_command and isinstance(install_command[0], list):
            for step in install_command:
                manage_services.run_command(step, cwd, env)
        else:
            manage_services.run_command(install_command, cwd, env)
    return cwd, env


def start_service_temp(service: dict, cwd: Path, env: dict[str, str]) -> subprocess.Popen[str]:
    if service.get("ready_port") and manage_services.is_port_in_use(int(service["ready_port"])):
        raise RuntimeError(f"{service['name']} cannot start because port {service['ready_port']} is already in use")
    process = manage_services.spawn_service(service, cwd, env)
    ready_port = service.get("ready_port")
    if ready_port:
        manage_services.wait_for_port(int(ready_port))
        manage_services.log(f"{service['name']} is ready on port {ready_port}")
    healthcheck_url = service.get("healthcheck_url")
    if healthcheck_url:
        manage_services.wait_for_healthcheck(str(healthcheck_url))
        manage_services.log(f"{service['name']} passed healthcheck {healthcheck_url}")
    return process


def stop_service_temp(service: dict, process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
    manage_services.log(f"stopped temporary {service['name']} process")


def run_login_script(script_name: str) -> None:
    manage_services.run_command([sys.executable, f"scripts/{script_name}"], ROOT_DIR, os.environ.copy())


def current_global_env() -> dict[str, str]:
    payload = service_env_store.load_local_config()
    return {str(k): str(v) for k, v in payload.get("global_env", {}).items()}


def current_service_env(service_name: str) -> dict[str, str]:
    payload = service_env_store.load_local_config()
    services = payload.get("services", {})
    service = services.get(service_name, {})
    return {str(k): str(v) for k, v in service.get("env", {}).items()}


def main() -> int:
    args = parse_args()
    ensure_local_config_exists()
    services, global_env, overrides = load_manifest_map()

    manage_services.log("scanning environment and preparing repositories")
    prepared: list[tuple[dict, Path, dict[str, str]]] = []
    wechat_cwd: Path | None = None
    wechat_env: dict[str, str] | None = None
    for service_name in ("wechat_exporter", "mediacrawler_xhs", "backend"):
        service = services[service_name]
        cwd, env = install_service_without_env_gate(
            service,
            global_env,
            overrides,
            update=not args.no_update,
            skip_install=args.skip_install,
        )
        prepared.append((service, cwd, env))
        if service_name == "wechat_exporter":
            wechat_cwd = cwd
            wechat_env = env

    wechat_process: subprocess.Popen[str] | None = None
    promoted_existing_processes: list[tuple[dict, subprocess.Popen[str]]] = []
    try:
        if not args.skip_wechat_login:
            wechat_key = current_global_env().get("WECHAT_EXPORTER_API_KEY", "").strip()
            if not wechat_key or wechat_key == "filled-by-login-wechat-script":
                manage_services.log("starting temporary wechat exporter service for QR login")
                if wechat_cwd is None or wechat_env is None:
                    raise RuntimeError("wechat_exporter preparation did not produce a runnable service context")
                wechat_process = start_service_temp(services["wechat_exporter"], wechat_cwd, wechat_env)
                run_login_script("wechat_terminal_login.py")
                promoted_existing_processes.append((services["wechat_exporter"], wechat_process))
        if not args.skip_xhs_login:
            xhs_cookie = current_service_env("mediacrawler_xhs").get("XHS_MEDIACRAWLER_COOKIES", "").strip()
            if not xhs_cookie:
                manage_services.log("starting Xiaohongshu terminal login")
                run_login_script("xhs_login_only.py")

        manage_services.log("starting full stack")
        manage_services.start_prepared_services(
            prepared,
            existing_processes=promoted_existing_processes,
        )
    finally:
        if wechat_process is not None and not promoted_existing_processes:
            stop_service_temp(services["wechat_exporter"], wechat_process)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
