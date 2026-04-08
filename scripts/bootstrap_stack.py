#!/usr/bin/env python3
"""Single-entry bootstrap for environment scan, install, QR login, and full stack startup."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import manage_services
import service_env_store


ROOT_DIR = Path(__file__).resolve().parents[1]


STATUS_LABELS = {
    "prepared": "已准备",
    "reused": "已复用",
    "ok": "正常",
    "repaired": "已修复",
    "skipped": "已跳过",
    "ready": "即将启动",
    "pending": "待执行",
    "failed": "失败",
}

SECTION_LABELS = {
    "services": "服务准备",
    "checks": "登录与校验",
    "startup": "启动流程",
}


def add_report_entry(report: dict[str, list[dict[str, str]]], section: str, name: str, status: str, detail: str) -> None:
    report.setdefault(section, []).append(
        {
            "name": name,
            "status": status,
            "detail": detail,
        }
    )


def print_preflight_report(report: dict[str, list[dict[str, str]]]) -> None:
    manage_services.log("启动前自检摘要")
    for section in ("services", "checks", "startup"):
        entries = report.get(section, [])
        if not entries:
            continue
        manage_services.log(f"  {SECTION_LABELS.get(section, section)}:")
        for entry in entries:
            status_label = STATUS_LABELS.get(entry["status"], entry["status"])
            manage_services.log(f"    - {entry['name']}: {status_label} | {entry['detail']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap the full stack: scan environment, install deps, run QR logins, then start all services."
    )
    parser.add_argument("--no-update", action="store_true", help="Skip pulling updates for clean managed repositories.")
    parser.add_argument("--skip-install", action="store_true", help="Skip dependency installation and only prepare/start services.")
    parser.add_argument("--skip-wechat-login", action="store_true", help="Skip the WeChat QR login step.")
    parser.add_argument(
        "--interactive-wechat-login",
        action="store_true",
        help="If WeChat login is invalid, run the terminal QR login flow before continuing startup.",
    )
    parser.add_argument(
        "--interactive-platform-logins",
        action="store_true",
        help="If crawler platform logins are invalid, run their interactive login flows before continuing startup.",
    )
    parser.add_argument("--skip-xhs-login", action="store_true", help="Skip the Xiaohongshu QR login step.")
    parser.add_argument("--skip-weibo-login", action="store_true", help="Skip the Weibo QR login step.")
    parser.add_argument("--skip-douyin-login", action="store_true", help="Skip the Douyin QR login step.")
    parser.add_argument("--skip-bilibili-login", action="store_true", help="Skip the Bilibili QR login step.")
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
    report: dict[str, list[dict[str, str]]] | None = None,
) -> tuple[Path, dict[str, str]]:
    manage_services.ensure_required_binaries(service)
    if manage_services.service_is_healthy(service):
        cwd = manage_services.resolve_service_cwd(service)
        env = manage_services.merged_env(service, global_env, overrides)
        manage_services.ensure_required_env(service, env)
        if report is not None:
            detail = f"{service['kind']} @ {cwd} | reused running service | skipped update + install"
            add_report_entry(report, "services", service["name"], "reused", detail)
        return cwd, env
    if service["kind"] == "managed_repo":
        cwd = manage_services.ensure_managed_repo(service, update=update)
    else:
        cwd = manage_services.resolve_service_cwd(service)
    env = manage_services.merged_env(service, global_env, overrides)
    manage_services.ensure_required_env(service, env)
    install_command = service.get("install")
    if install_command and not skip_install:
        if install_command and isinstance(install_command[0], list):
            for step in install_command:
                manage_services.run_command(step, cwd, env)
        else:
            manage_services.run_command(install_command, cwd, env)
    if service["name"] == "mediacrawler_xhs" and not skip_install:
        manage_services.run_command(
            [sys.executable, "scripts/ensure_mediacrawler_xhs_dependency.py", "--repo", str(cwd)],
            ROOT_DIR,
            os.environ.copy(),
        )
    if report is not None:
        detail = f"{service['kind']} @ {cwd}"
        if skip_install:
            detail += " | install skipped"
        elif service["name"] == "mediacrawler_xhs":
            detail += " | dependencies synced + xhshow ensured"
        else:
            detail += " | dependencies ready"
        add_report_entry(report, "services", service["name"], "prepared", detail)
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


def run_login_script(script_name: str, *script_args: str) -> None:
    manage_services.run_command(
        [sys.executable, f"scripts/{script_name}", *script_args],
        ROOT_DIR,
        os.environ.copy(),
    )


def run_json_script(script_name: str, *script_args: str) -> dict:
    completed = subprocess.run(
        [sys.executable, f"scripts/{script_name}", *script_args],
        cwd=ROOT_DIR,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=180,
    )
    stdout = completed.stdout.strip() or "{}"
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{script_name} returned invalid JSON: {stdout[:200] or completed.stderr[:200] or 'empty output'}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{script_name} returned an unexpected payload")
    return payload


def current_global_env() -> dict[str, str]:
    payload = service_env_store.load_local_config()
    return {str(k): str(v) for k, v in payload.get("global_env", {}).items()}


def current_service_env(service_name: str) -> dict[str, str]:
    payload = service_env_store.load_local_config()
    services = payload.get("services", {})
    service = services.get(service_name, {})
    return {str(k): str(v) for k, v in service.get("env", {}).items()}


def service_is_already_running(service: dict) -> bool:
    return manage_services.service_is_healthy(service)


def ensure_wechat_login(
    service: dict,
    cwd: Path,
    env: dict[str, str],
    *,
    interactive_refresh: bool = False,
    report: dict[str, list[dict[str, str]]] | None = None,
) -> subprocess.Popen[str] | None:
    process: subprocess.Popen[str] | None = None
    if service_is_already_running(service):
        manage_services.log("reusing existing wechat exporter service for login validation")
        if report is not None:
            add_report_entry(report, "startup", "wechat_exporter", "ready", "复用已在运行的 3000 端口服务")
    else:
        manage_services.log("starting temporary wechat exporter service for login validation")
        process = start_service_temp(service, cwd, env)
    status = run_json_script("wechat_login_status.py")
    if bool(status.get("ok")):
        manage_services.log("wechat login is valid")
        if report is not None:
            add_report_entry(report, "checks", "wechat login", "ok", "existing login is still valid")
        return process

    previous_reason = str(status.get("reason") or "unknown")
    manage_services.log(f"wechat login requires refresh: {previous_reason}")
    if not interactive_refresh:
        manage_services.log("wechat login requires manual refresh in the web console; continuing startup")
        if report is not None:
            add_report_entry(
                report,
                "checks",
                "wechat login",
                "skipped",
                f"{previous_reason}; finish login from the web console after startup",
            )
        return process
    run_login_script("wechat_terminal_login.py")
    status = run_json_script("wechat_login_status.py")
    if not bool(status.get("ok")):
        raise RuntimeError(f"wechat login validation failed after refresh: {status.get('reason') or 'unknown'}")
    manage_services.log("wechat login refreshed successfully")
    if report is not None:
        add_report_entry(report, "checks", "wechat login", "repaired", f"refreshed from {previous_reason}")
    return process


def ensure_mediacrawler_platform_login(
    platform: str,
    *,
    interactive_refresh: bool = False,
    report: dict[str, list[dict[str, str]]] | None = None,
) -> None:
    status = run_json_script("mediacrawler_login_status.py", "--platforms", platform)
    if bool(status.get("ok")):
        manage_services.log(f"{platform} login is valid")
        if report is not None:
            add_report_entry(report, "checks", f"{platform} login", "ok", "existing login is still valid")
        return

    previous_reason = str(status.get("reason") or "unknown")
    manage_services.log(f"{platform} login requires refresh: {previous_reason}")
    if not interactive_refresh:
        manage_services.log(f"{platform} login requires manual refresh in the web console; continuing startup")
        if report is not None:
            add_report_entry(
                report,
                "checks",
                f"{platform} login",
                "skipped",
                f"{previous_reason}; finish login from the web console after startup",
            )
        return
    run_login_script("mediacrawler_terminal_login.py", "--platform", platform)
    status = run_json_script("mediacrawler_login_status.py", "--platforms", platform)
    if not bool(status.get("ok")):
        raise RuntimeError(f"{platform} login validation failed after refresh: {status.get('reason') or 'unknown'}")
    manage_services.log(f"{platform} login refreshed successfully")
    if report is not None:
        add_report_entry(report, "checks", f"{platform} login", "repaired", f"refreshed from {previous_reason}")


def main() -> int:
    args = parse_args()
    ensure_local_config_exists()
    services, global_env, overrides = load_manifest_map()
    report: dict[str, list[dict[str, str]]] = {"services": [], "checks": [], "startup": []}
    add_report_entry(
        report,
        "startup",
        "mode",
        "pending",
        f"update={'off' if args.no_update else 'on'}, install={'off' if args.skip_install else 'on'}",
    )

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
            report=report,
        )
        prepared.append((service, cwd, env))
        if service_name == "wechat_exporter":
            wechat_cwd = cwd
            wechat_env = env

    wechat_process: subprocess.Popen[str] | None = None
    promoted_existing_processes: list[tuple[dict, subprocess.Popen[str]]] = []
    try:
        if not args.skip_wechat_login:
            if wechat_cwd is None or wechat_env is None:
                raise RuntimeError("wechat_exporter preparation did not produce a runnable service context")
            wechat_process = ensure_wechat_login(
                services["wechat_exporter"],
                wechat_cwd,
                wechat_env,
                interactive_refresh=args.interactive_wechat_login,
                report=report,
            )
            if wechat_process is not None:
                promoted_existing_processes.append((services["wechat_exporter"], wechat_process))
        else:
            add_report_entry(report, "checks", "wechat login", "skipped", "skip flag enabled")
        if not args.skip_xhs_login:
            ensure_mediacrawler_platform_login(
                "xhs",
                interactive_refresh=args.interactive_platform_logins,
                report=report,
            )
        else:
            add_report_entry(report, "checks", "xhs login", "skipped", "skip flag enabled")
        if not args.skip_weibo_login:
            ensure_mediacrawler_platform_login(
                "weibo",
                interactive_refresh=args.interactive_platform_logins,
                report=report,
            )
        else:
            add_report_entry(report, "checks", "weibo login", "skipped", "skip flag enabled")
        if not args.skip_douyin_login:
            ensure_mediacrawler_platform_login(
                "douyin",
                interactive_refresh=args.interactive_platform_logins,
                report=report,
            )
        else:
            add_report_entry(report, "checks", "douyin login", "skipped", "skip flag enabled")
        if not args.skip_bilibili_login:
            ensure_mediacrawler_platform_login(
                "bilibili",
                interactive_refresh=args.interactive_platform_logins,
                report=report,
            )
        else:
            add_report_entry(report, "checks", "bilibili login", "skipped", "skip flag enabled")

        add_report_entry(report, "startup", "next step", "ready", "starting managed services")
        print_preflight_report(report)

        manage_services.log("starting full stack")
        manage_services.start_prepared_services(
            prepared,
            existing_processes=promoted_existing_processes,
        )
    except Exception as exc:
        add_report_entry(report, "startup", "bootstrap", "failed", str(exc))
        print_preflight_report(report)
        raise
    finally:
        if wechat_process is not None and not promoted_existing_processes:
            stop_service_temp(services["wechat_exporter"], wechat_process)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
