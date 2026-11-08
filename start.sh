#!/usr/bin/env bash
set -euo pipefail

# Start the Summary AI backend (FastAPI, port 8001) and web frontend (port 3333).
# PIDs are written to /tmp/open-smry-*.pid so stop.sh can kill them.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_API="/tmp/open-smry-api.pid"
PID_WEB="/tmp/open-smry-web.pid"

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

# Kill any orphaned processes holding our ports.
for port in 8001 3333; do
  if fuser "$port/tcp" >/dev/null 2>&1; then
    echo "Port $port is in use by an orphaned process — killing it..."
    fuser -k "$port/tcp" 2>/dev/null || true
    sleep 1
  fi
done

echo "Starting Summary AI backend (FastAPI) on http://localhost:8001..."
pnpm run dev:api > /tmp/open-smry-api.log 2>&1 &
echo $! > "$PID_API"

echo "Starting Summary AI web server on http://localhost:3333..."
pnpm run dev:web > /tmp/open-smry-web.log 2>&1 &
echo $! > "$PID_WEB"

echo ""
echo "Started:"
echo "  Backend API : http://localhost:8001   (PID $(cat "$PID_API"), logs: /tmp/open-smry-api.log)"
echo "  Web UI      : http://localhost:3333   (PID $(cat "$PID_WEB"), logs: /tmp/open-smry-web.log)"
echo ""
echo "Stop with: ./stop.sh"
