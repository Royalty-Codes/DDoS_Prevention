#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export SDN_DDOS_GIT_COMMIT="$(git rev-parse HEAD)"
export RYU_MANAGER="${RYU_MANAGER:-/opt/sdn-ddos-ryu-venv/bin/ryu-manager}"
export RYU_PYTHON="${RYU_PYTHON:-/opt/sdn-ddos-ryu-venv/bin/python}"
exec python -m sdn_ddos.cli smoke --run-dir "${1:-runs/smoke}"
