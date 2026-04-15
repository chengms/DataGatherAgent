#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
WATCH_SCRIPT="$ROOT_DIR/scripts/run_with_watch.py"
. "$ROOT_DIR/scripts/python_cmd.sh"
PYTHON_BIN="$(resolve_python "$BACKEND_DIR")"

"$PYTHON_BIN" "$WATCH_SCRIPT" --timeout 1800 --idle-timeout 300 --heartbeat 30 --cwd "$BACKEND_DIR" -- "$PYTHON_BIN" -m unittest discover -s tests -v
