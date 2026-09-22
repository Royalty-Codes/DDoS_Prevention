#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export SDN_TELEMETRY_PATH="${SDN_TELEMETRY_PATH:-data/raw/openflow_telemetry.jsonl}"
exec python3 network/controller/run_ryu.py network/controller/ryu_ddos_controller.py --observe-links