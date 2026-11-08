#!/usr/bin/env bash
set -euo pipefail

# Stop the Summary AI backend and web frontend started by start.sh.

PID_API="/tmp/open-smry-api.pid"
PID_WEB="/tmp/open-smry-web.pid"

stop_pid() {
  local pid_file="$1"
  local name="$2"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "Stopping $name (PID $pid)..."
      kill "$pid" 2>/dev/null || true
      # Give it a moment, then force-kill if still alive.
      sleep 1
      if kill -0 "$pid" 2>/dev/null; then
        echo "Force-killing $name (PID $pid)..."
        kill -9 "$pid" 2>/dev/null || true
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
