#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ryu-manager "$ROOT/controller/ryu_controller.py"
