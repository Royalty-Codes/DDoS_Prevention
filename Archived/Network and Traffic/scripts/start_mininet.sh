#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PYTHONPATH="$ROOT/topology${PYTHONPATH:+:$PYTHONPATH}"
sudo mn --custom "$ROOT/topology/sdn_topology.py" --topo SdnDdosTopology --switch ovsk,protocols=OpenFlow13 --controller remote,ip=127.0.0.1,port=6653
