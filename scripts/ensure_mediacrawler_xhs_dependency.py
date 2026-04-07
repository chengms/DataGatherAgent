#!/usr/bin/env python3
"""Ensure MediaCrawler's virtualenv has the Xiaohongshu signature dependency installed."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPO = ROOT_DIR / "external_tools" / "MediaCrawler"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ensure xhshow is installed into MediaCrawler's virtualenv.")
    parser.add_argument("--repo", default=str(DEFAULT_REPO))
    parser.add_argument("--package", default="xhshow")
    return parser.parse_args()


def repo_python(repo_dir: Path) -> Path:
    return repo_dir / ".venv" / ("Scripts" if sys.platform.startswith("win") else "bin") / ("python.exe" if sys.platform.startswith("win") else "python")


def package_installed(python_path: Path, package_name: str) -> bool:
    completed = subprocess.run(
        [str(python_path), "-c", f"import importlib.util; print(importlib.util.find_spec('{package_name}') is not None)"],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode == 0 and completed.stdout.strip() == "True"


def main() -> int:
    args = parse_args()
    repo_dir = Path(args.repo).resolve()
    python_path = repo_python(repo_dir)
    if not repo_dir.exists():
        raise RuntimeError(f"managed MediaCrawler checkout does not exist: {repo_dir}")
    if not python_path.exists():
        raise RuntimeError(f"managed MediaCrawler virtualenv Python is missing: {python_path}")
    if package_installed(python_path, args.package):
        print(f"{args.package} already installed", flush=True)
        return 0

    completed = subprocess.run(
        ["uv", "pip", "install", "--python", str(python_path), args.package],
        cwd=repo_dir,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"failed to install {args.package} into MediaCrawler environment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
