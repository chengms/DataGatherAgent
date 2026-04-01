#!/usr/bin/env python3
"""Run a command with timeout and no-output heartbeat reporting."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a command and emit heartbeat logs when it stays silent."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=0,
        help="Hard timeout in seconds. 0 disables the timeout.",
    )
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=0,
        help="Kill the command if it produces no output for this many seconds. 0 disables it.",
    )
    parser.add_argument(
        "--heartbeat",
        type=float,
        default=30,
        help="Print a heartbeat if the command is silent for this many seconds.",
    )
    parser.add_argument(
        "--cwd",
        default=".",
        help="Working directory for the child process.",
    )
    parser.add_argument(
        "--shell",
        action="store_true",
        help="Run the command through the shell.",
    )
    parser.add_argument(
        "--no-timestamps",
        action="store_true",
        help="Disable timestamps in monitor logs.",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to run. Use -- before the command.",
    )
    args = parser.parse_args()
    if not args.command:
        parser.error("missing command; pass it after --")
    if args.command[0] == "--":
        args.command = args.command[1:]
    return args


def format_prefix(use_timestamps: bool) -> str:
    if not use_timestamps:
        return "[watch]"
    return f"[watch {time.strftime('%Y-%m-%d %H:%M:%S')}]"


def log(message: str, *, use_timestamps: bool) -> None:
    print(f"{format_prefix(use_timestamps)} {message}", flush=True)


def stream_output(pipe, sink, state: dict[str, float]) -> None:
    try:
        for line in iter(pipe.readline, ""):
            if not line:
                break
            state["last_output"] = time.monotonic()
            sink.write(line)
            sink.flush()
    finally:
        pipe.close()


def describe_command(command: list[str], use_shell: bool) -> str:
    if use_shell:
        return " ".join(command)
    return shlex.join(command)


def build_env(command: list[str], use_shell: bool) -> dict[str, str]:
    env = os.environ.copy()
    if not use_shell and command:
        executable = Path(command[0]).name.lower()
        if executable in {"python", "python.exe", "python3", "py"}:
            env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def main() -> int:
    args = parse_args()
    command = args.command
    workdir = str(Path(args.cwd).resolve())
    use_timestamps = not args.no_timestamps
    if args.shell:
        popen_command: str | list[str] = " ".join(command)
    else:
        popen_command = command

    log(f"starting command in {workdir}", use_timestamps=use_timestamps)
    log(
        f"command: {describe_command(command, args.shell)}",
        use_timestamps=use_timestamps,
    )

    process = subprocess.Popen(
        popen_command,
        cwd=workdir,
        shell=args.shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
        env=build_env(command, args.shell),
    )

    state = {"started": time.monotonic(), "last_output": time.monotonic()}
    stdout_thread = threading.Thread(
        target=stream_output, args=(process.stdout, sys.stdout, state), daemon=True
    )
    stderr_thread = threading.Thread(
        target=stream_output, args=(process.stderr, sys.stderr, state), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()

    last_heartbeat_at = state["last_output"]
    timed_out = False
    idle_timed_out = False

    while process.poll() is None:
        time.sleep(1)
        now = time.monotonic()
        runtime = now - state["started"]
        idle = now - state["last_output"]

        if args.timeout and runtime >= args.timeout:
            timed_out = True
            log(
                f"hard timeout reached after {runtime:.0f}s; terminating process",
                use_timestamps=use_timestamps,
            )
            process.terminate()
            break

        if args.idle_timeout and idle >= args.idle_timeout:
            idle_timed_out = True
            log(
                f"idle timeout reached after {idle:.0f}s without output; terminating process",
                use_timestamps=use_timestamps,
            )
            process.terminate()
            break

        if args.heartbeat and (now - max(last_heartbeat_at, state["last_output"])) >= args.heartbeat:
            log(
                f"still running: runtime={runtime:.0f}s idle={idle:.0f}s pid={process.pid}",
                use_timestamps=use_timestamps,
            )
            last_heartbeat_at = now

    try:
        exit_code = process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        log("process did not exit after terminate; killing it", use_timestamps=use_timestamps)
        process.kill()
        exit_code = process.wait()

    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)

    runtime = time.monotonic() - state["started"]
    if timed_out:
        log(
            f"finished with forced stop after {runtime:.0f}s",
            use_timestamps=use_timestamps,
        )
        return 124
    if idle_timed_out:
        log(
            f"finished with idle stop after {runtime:.0f}s",
            use_timestamps=use_timestamps,
        )
        return 125

    log(
        f"process exited with code {exit_code} after {runtime:.0f}s",
        use_timestamps=use_timestamps,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
