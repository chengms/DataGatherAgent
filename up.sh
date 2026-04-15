#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
. "$ROOT_DIR/scripts/python_cmd.sh"
PYTHON_BIN="$(resolve_python)"
"$PYTHON_BIN" scripts/bootstrap_stack.py
