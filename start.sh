#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
WATCH_SCRIPT="$ROOT_DIR/scripts/run_with_watch.py"
BOOTSTRAP_SCRIPT="$ROOT_DIR/scripts/ensure_backend_ready.py"

python "$WATCH_SCRIPT" --timeout 1800 --idle-timeout 300 --heartbeat 30 --cwd "$BACKEND_DIR" -- python "$BOOTSTRAP_SCRIPT"
python "$WATCH_SCRIPT" --heartbeat 30 --cwd "$BACKEND_DIR" -- python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
