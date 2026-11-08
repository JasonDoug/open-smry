#!/usr/bin/env bash
set -euo pipefail

# Start the Summary AI backend (FastAPI, port 8001) and web frontend (port 3333).
# PID/log files live in a private, user-owned runtime directory.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

RUNTIME_DIR="${XDG_RUNTIME_DIR:-$HOME/.cache}/open-smry"
mkdir -p "$RUNTIME_DIR"
PID_API="$RUNTIME_DIR/api.pid"
PID_WEB="$RUNTIME_DIR/web.pid"

# Sanity-check that required tooling is available.
if ! command -v pnpm >/dev/null 2>&1; then
  echo "ERROR: pnpm not found on PATH" >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv not found on PATH" >&2
  exit 1
fi

# Don't start if already running (tracked PIDs).
if [[ -f "$PID_API" ]] && kill -0 "$(cat "$PID_API")" 2>/dev/null; then
  echo "Backend already running (PID $(cat "$PID_API")). Use ./stop.sh first or ./restart.sh."
  exit 1
fi
if [[ -f "$PID_WEB" ]] && kill -0 "$(cat "$PID_WEB")" 2>/dev/null; then
  echo "Web server already running (PID $(cat "$PID_WEB")). Use ./stop.sh first or ./restart.sh."
  exit 1
fi

# Reclaim ports only from orphaned processes that belong to THIS project;
# never kill unrelated services that happen to listen on 8001/3333.
for port in 8001 3333; do
  pids="$(fuser "$port/tcp" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    mine=0
    for pid in $pids; do
      if tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -q "open-smry\|uvicorn app.main\|apps/web/server.mjs"; then
        mine=1
      fi
    done
    if [[ "$mine" == 1 ]]; then
      echo "Port $port is held by an orphaned open-smry process — killing it..."
      fuser -k "$port/tcp" 2>/dev/null || true
      sleep 1
    else
      echo "ERROR: port $port is in use by an unrelated process (pids: $pids). Free it manually and retry." >&2
      exit 1
    fi
  fi
done

echo "Starting Summary AI backend (FastAPI) on http://localhost:8001..."
pnpm run dev:api > "$RUNTIME_DIR/api.log" 2>&1 &
echo $! > "$PID_API"

# Pin the web server's port so an exported PORT (used by the backend) cannot move it.
echo "Starting Summary AI web server on http://localhost:3333..."
PORT=3333 pnpm run dev:web > "$RUNTIME_DIR/web.log" 2>&1 &
echo $! > "$PID_WEB"

echo ""
echo "Started:"
echo "  Backend API : http://localhost:8001   (PID $(cat "$PID_API"), logs: $RUNTIME_DIR/api.log)"
echo "  Web UI      : http://localhost:3333   (PID $(cat "$PID_WEB"), logs: $RUNTIME_DIR/web.log)"
echo ""
echo "Stop with: ./stop.sh"
