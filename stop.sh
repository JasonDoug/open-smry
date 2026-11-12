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
  # start.sh records the `pnpm run dev:*` launcher, whose cmdline names no
  # project path — so also accept processes running from this repo directory.
  [[ "$(readlink "/proc/$pid/cwd" 2>/dev/null)" == "$ROOT_DIR" ]] && return 0
  tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -q "open-smry\|uvicorn app.main\|apps/web/server.mjs"
}

# start.sh launches each service via setsid, so the recorded PID leads its own
# process group: signal the whole group so uvicorn/node children stop too.
signal_service() {
  local sig="$1" pid="$2"
  if [[ "$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')" == "$pid" ]]; then
    kill "-$sig" -- "-$pid" 2>/dev/null || true
  else
    kill "-$sig" "$pid" 2>/dev/null || true
  fi
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
        signal_service TERM "$pid"
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
          echo "Force-killing $name (PID $pid)..."
          signal_service KILL "$pid"
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
