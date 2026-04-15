#!/usr/bin/env bash
set -euo pipefail

resolve_python() {
  local preferred_dir="${1:-}"
  if [ -n "$preferred_dir" ]; then
    if [ -x "$preferred_dir/.venv/bin/python" ]; then
      printf '%s\n' "$preferred_dir/.venv/bin/python"
      return 0
    fi
    if [ -x "$preferred_dir/.venv/Scripts/python.exe" ]; then
      printf '%s\n' "$preferred_dir/.venv/Scripts/python.exe"
      return 0
    fi
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  if command -v python3.11 >/dev/null 2>&1; then
    command -v python3.11
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  echo "No usable Python interpreter found. Install Python 3.11+ or expose python/python3.11 in PATH." >&2
  return 1
}
