#!/usr/bin/env python3
"""Start MediaCrawler via its repo-local interpreter when available."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the MediaCrawler API service.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default="8080")
    parser.add_argument("--reload", action="store_true")
    return parser.parse_args()


def repo_python(repo_dir: Path) -> Path | None:
    candidates = [
        repo_dir / ".venv" / "Scripts" / "python.exe",
        repo_dir / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    args = parse_args()
    repo_dir = Path(args.repo).resolve()
    python_bin = repo_python(repo_dir)
    command: list[str]
    if python_bin is not None:
        command = [
            str(python_bin),
            "-m",
            "uvicorn",
            "api.main:app",
            "--host",
            args.host,
            "--port",
            str(args.port),
        ]
    else:
        uv_bin = shutil.which("uv")
        if not uv_bin:
            raise RuntimeError("uv is not installed and MediaCrawler .venv was not found")
        command = [
            uv_bin,
            "run",
            "uvicorn",
            "api.main:app",
            "--host",
            args.host,
            "--port",
            str(args.port),
        ]
    if args.reload:
        command.append("--reload")

    completed = subprocess.run(command, cwd=repo_dir, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
