#!/usr/bin/env bash
set -euo pipefail

# Stop the Summary AI backend and web frontend started by start.sh.
# A recorded PID is only signalled when it still belongs to an open-smry process,
# guarding against PID reuse pointing at an unrelated process.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-$HOME/.cache}/open-smry"
PID_API="$RUNTIME_DIR/api.pid"
PID_WEB="$RUNTIME_DIR/web.pid"

belongs_to_project() {
  local pid="$1"
  tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -q "open-smry\|uvicorn app.main\|apps/web/server.mjs"
}

stop_pid() {
  local pid_file="$1"
  local name="$2"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      if belongs_to_project "$pid"; then
        echo "Stopping $name (PID $pid)..."
        kill "$pid" 2>/dev/null || true
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
          echo "Force-killing $name (PID $pid)..."
          kill -9 "$pid" 2>/dev/null || true
        fi
      else
        echo "$name PID $pid no longer belongs to open-smry (PID reuse?) — leaving it untouched."
      fi
    else
      echo "$name (PID $pid) was not running."
    fi
    rm -f "$pid_file"
  else
    echo "$name PID file not found ($pid_file)."
  fi
}

stop_pid "$PID_API" "backend"
stop_pid "$PID_WEB" "web server"

echo ""
echo "Stopped Summary AI backend and web server."
