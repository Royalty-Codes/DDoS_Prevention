#!/usr/bin/env bash
set -euo pipefail

CONTROLLER_VENV="${SDN_DDOS_CONTROLLER_VENV:-/opt/sdn-ddos-ryu-venv}"
"$CONTROLLER_VENV/bin/python" -m pip install --no-build-isolation -r requirements-controller.txt
"$CONTROLLER_VENV/bin/ryu-manager" --version
