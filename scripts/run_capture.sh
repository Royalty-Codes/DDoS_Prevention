#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export SDN_DDOS_GIT_COMMIT="$(git rev-parse HEAD)"
export RYU_MANAGER="${RYU_MANAGER:-/opt/sdn-ddos-ryu-venv/bin/ryu-manager}"
export RYU_PYTHON="${RYU_PYTHON:-/opt/sdn-ddos-ryu-venv/bin/python}"
exec python -m sdn_ddos.cli capture --run-dir "${1:?usage: scripts/run_capture.sh RUN_DIR}" --rows-per-class "${ROWS_PER_CLASS:-10000}" --resume
