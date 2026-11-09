#!/usr/bin/env bash
set -euo pipefail

# Restart the Summary AI backend and web frontend.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "Stopping existing servers..."
./stop.sh || true

echo "Starting servers..."
./start.sh
