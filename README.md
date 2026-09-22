# SDN DDoS Lab — Phase 1: Measured Dataset Generation

This repository is being rebuilt around one honest first target: a local-only
Mininet + Open vSwitch + Ryu lab that records measured SDN telemetry. It does
not generate NumPy/Pandas traffic profiles.

## Dataset contract

The canonical dataset has **110,000 rows**, **28 columns**, and **11 balanced
classes** (10,000 rows each):

`BENIGN`, `UDP_FLOOD`, `ICMP_FLOOD`, `UDP_AMPLIFICATION_STYLE`, `SYN_FLOOD`,
`PING_OF_DEATH_STYLE`, `SMURF_STYLE`, `HTTP_FLOOD`, `SLOWLORIS_STYLE`,
`LAND_STYLE`, and `PACKET_IN_FLOOD_STYLE`.

The schema is defined once in `sdn_ddos/contracts.py`. Raw OVS/controller
observations are retained as resumable CSV shards, then converted to a
validated CSV and Parquet dataset without Pandas or NumPy.

## Lab architecture

The data plane is a dual-spine, multi-zone routed lab:

```text
clients ─ access OVS ─ zone router ─┐
attackers ─ access OVS ─ red router ├─ spine-a / spine-b ─ service router ─ service OVS ─ web/api/dns
branch clients ─ access OVS ─────────┘
```

All traffic stays within the Mininet address space `10.77.0.0/16`. The
`*_STYLE` labels are safe, bounded workload patterns; they do not send
spoofed, malformed, reflected, or external traffic.

## WSL setup

Run from a supported Ubuntu/WSL installation as root or through `sudo`:

```bash
sudo bash scripts/bootstrap_wsl.sh
export RYU_MANAGER=/opt/sdn-ddos-ryu-venv/bin/ryu-manager
export RYU_PYTHON=/opt/sdn-ddos-ryu-venv/bin/python
python3 -m sdn_ddos.cli preflight --strict
python3 -m sdn_ddos.cli smoke
python3 -m sdn_ddos.cli capture --run-dir runs/first-110k --rows-per-class 10000 --resume
/opt/sdn-ddos-ryu-venv/bin/python -m pip install -r requirements-lab.txt
/opt/sdn-ddos-ryu-venv/bin/python -m sdn_ddos.cli validate --run-dir runs/first-110k --write-final
```

`capture` is resumable. Each completed shard is atomic, and `--resume` only
captures missing class windows. Ryu runs in its own pinned Python 3.11
environment on the Linux filesystem while system Python runs Mininet.

## Colab capture notebook

Open `notebooks/01_colab_sdn_capture.ipynb`. Its first setup cell removes only
its own temporary clone, runs `git fetch --all --tags --prune`, then
`git pull --ff-only` from `origin/master` before every capture. It records the
resolved commit in the run manifest.

The notebook requires hosted Colab to grant the Linux network capabilities
needed by Mininet/OVS. Its preflight fails closed if they are unavailable; it
will never emit a synthetic substitute. Push the desired commit to `origin`
before starting Colab, otherwise Colab cannot fetch new local modules.

## Future scope

Kafka and Spark are deliberately not runtime dependencies of this first
milestone. `telemetry.v1` JSONL is the stable ingestion boundary that later
Kafka producers and Spark Structured Streaming consumers will use.
