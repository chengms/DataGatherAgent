#!/usr/bin/env python3
"""Skip backend editable install when runtime dependencies are already available."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
REQUIRED_MODULES = ("fastapi", "uvicorn", "pydantic", "requests", "bs4", "PIL")


def missing_modules() -> list[str]:
    missing: list[str] = []
    for module_name in REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            missing.append(module_name)
    return missing


def main() -> int:
    missing = missing_modules()
    if not missing:
        print("backend dependencies already available; skipping pip install", flush=True)
        return 0

    print(
        f"backend dependencies missing ({', '.join(missing)}); installing editable package",
        flush=True,
    )
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        cwd=BACKEND_DIR,
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
