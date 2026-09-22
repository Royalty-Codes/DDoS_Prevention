"""Orchestrate isolated Mininet traffic, OVS deltas, and Ryu journal snapshots."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifacts import ShardStore, append_jsonl, utc_now
from .contracts import DATASET_COLUMNS, DATA_SOURCE, LABELS, SCHEMA_VERSION, WINDOW_SECONDS, scenario_for
from .preflight import run_preflight
from .telemetry import ControllerJournal, OvsCounterCollector
from .tcp_flags import TcpFlagCounter
from .topology import controller_switch_id, mininet_switch_name, start_lab
from .traffic import LocalTrafficRunner, source_names


SOURCE_SWITCH = {
    "c1": "leaf-campus", "c2": "leaf-campus", "c3": "leaf-campus", "c4": "leaf-campus",
    "b1": "leaf-branch", "b2": "leaf-branch", "b3": "leaf-branch", "b4": "leaf-branch",
    "a1": "leaf-red", "a2": "leaf-red", "a3": "leaf-red", "a4": "leaf-red",
    "a5": "leaf-red", "a6": "leaf-red", "a7": "leaf-red", "a8": "leaf-red",
}


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            if connection.connect_ex((host, port)) == 0:
                return
        time.sleep(0.2)
    raise TimeoutError(f"Controller did not listen on {host}:{port}")


def start_controller(telemetry_path: Path) -> subprocess.Popen[str]:
    requested_manager = os.environ.get("RYU_MANAGER", "ryu-manager")
    manager = requested_manager if Path(requested_manager).is_file() else shutil.which(requested_manager)
    if manager is None:
        raise RuntimeError("ryu-manager is missing; set RYU_MANAGER to the compatible controller virtualenv binary")
    requested_python = os.environ.get("RYU_PYTHON")
    derived_python = Path(manager).with_name("python")
    controller_python = requested_python or (str(derived_python) if derived_python.is_file() else sys.executable)
    if not Path(controller_python).is_file():
        raise RuntimeError(f"RYU_PYTHON does not exist: {controller_python}")
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["SDN_DDOS_CONTROLLER_TELEMETRY"] = str(telemetry_path.resolve())
    log_path = telemetry_path.with_name("ryu.log")
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [controller_python, "-m", "sdn_ddos.controller.run_ryu", "sdn_ddos/controller/ryu_telemetry.py"],
        env=environment,
        text=True,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    _wait_for_port("127.0.0.1", 6653)
    return process


def stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def _record(
    experiment_id: str,
    label: str,
    index: int,
    source_host: str,
    ovs: Any,
    packet_in_count: int,
    controller_cpu_pct: float,
    tcp_syn_count: int,
    tcp_ack_count: int,
) -> dict[str, Any]:
    scenario = scenario_for(label)
    packet_count = int(ovs.packet_count)
    byte_count = int(ovs.byte_count)
    mean_packet_size = byte_count / packet_count if packet_count else 0.0
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": experiment_id,
        "scenario_id": f"{label.lower()}-{index:06d}",
        "switch_id": ovs.switch_id,
        "src_host": source_host,
        "dst_host": "web",
        "protocol": scenario.protocol,
        "application": scenario.application,
        "window_seconds": WINDOW_SECONDS,
        "packet_count": packet_count,
        "byte_count": byte_count,
        "flow_count": int(ovs.flow_count),
        "packet_rate": packet_count / WINDOW_SECONDS,
        "byte_rate": byte_count / WINDOW_SECONDS,
        "flow_rate": int(ovs.flow_count) / WINDOW_SECONDS,
        "mean_packet_size": mean_packet_size,
        "tcp_syn_count": tcp_syn_count,
        "tcp_ack_count": tcp_ack_count,
        "tcp_handshake_completion_ratio": 0.0 if tcp_syn_count == 0 else tcp_ack_count / tcp_syn_count,
        "flow_table_size": int(ovs.flow_table_size),
        "packet_in_count": packet_in_count,
        "controller_cpu_proxy_pct": controller_cpu_pct,
        "attack_intensity": scenario.intensity,
        "attacker_count": scenario.attackers,
        "background_traffic_level": scenario.background,
        "label": scenario.label,
        "attack_family": scenario.family,
        "data_source": DATA_SOURCE,
    }


def _wait_for_controller_snapshot(journal: ControllerJournal, switch_name: str, timeout: float = 15.0) -> None:
    """Wait for a real Ryu flow reply instead of writing zero controller data."""

    controller_id = controller_switch_id(switch_name)
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            journal.interval(controller_id)
            return
        except RuntimeError as error:
            last_error = error
            time.sleep(0.25)
    raise RuntimeError(f"Controller never produced telemetry for {switch_name}") from last_error


def capture(args: argparse.Namespace) -> None:
    """Capture exact per-label quotas, resuming only rows absent from disk."""

    run_preflight(strict=True)
    run_dir = Path(args.run_dir).resolve()
    experiment_id = args.experiment_id or f"mininet-ovs-ryu-{int(time.time())}"
    store = ShardStore(run_dir, experiment_id=experiment_id, shard_size=args.shard_size)
    completed = store.completed_counts() if args.resume else {label: 0 for label in LABELS}
    if not args.resume and any(completed.values()):
        raise RuntimeError(f"Run directory already has shards. Use --resume or choose a new --run-dir: {run_dir}")
    store.write_manifest(
        started_utc=utc_now(),
        rows_per_class=args.rows_per_class,
        labels=list(LABELS),
        dataset_columns=list(DATASET_COLUMNS),
        data_source=DATA_SOURCE,
        schema_version=SCHEMA_VERSION,
        git_commit=os.environ.get("SDN_DDOS_GIT_COMMIT", "unknown"),
    )

    controller_path = run_dir / "raw" / "controller_telemetry.jsonl"
    controller: subprocess.Popen[str] | None = None
    network: Any | None = None
    background: Any | None = None
    tcp_counter: TcpFlagCounter | None = None
    try:
        controller = start_controller(controller_path)
        network = start_lab()
        runner = LocalTrafficRunner(network)
        runner.start_services()
        background = runner.start_background()
        tcp_counter = TcpFlagCounter(network.get("web"))
        tcp_counter.start()
        collector = OvsCounterCollector()
        journal = ControllerJournal(controller_path)
        # Prime OVS deltas and wait for the monitor to emit a usable controller snapshot.
        for switch_name in ("leaf-campus", "leaf-branch", "leaf-red"):
            collector.sample(network.get(mininet_switch_name(switch_name)))
        for switch_name in ("leaf-campus", "leaf-branch", "leaf-red"):
            _wait_for_controller_snapshot(journal, switch_name)

        while any(completed.get(label, 0) < args.rows_per_class for label in LABELS):
            for label in LABELS:
                index = int(completed.get(label, 0))
                if index >= args.rows_per_class:
                    continue
                scenario = scenario_for(label)
                expected_source = source_names(scenario, index)[0]
                switch_name = SOURCE_SWITCH[expected_source]
                switch = network.get(mininet_switch_name(switch_name))
                collector.sample(switch)
                journal.interval(controller_switch_id(switch_name))  # Prime Packet-In delta before traffic.
                tcp_before = tcp_counter.snapshot()
                session, source_host = runner.start(scenario, index)
                started = time.monotonic()
                try:
                    time.sleep(max(0.0, WINDOW_SECONDS - (time.monotonic() - started)))
                finally:
                    session.stop()
                ovs = collector.sample(switch)
                packet_in, cpu_pct, controller_table_size = journal.interval(controller_switch_id(switch_name))
                tcp_delta = tcp_counter.delta(tcp_before)
                if ovs.packet_count <= 0:
                    append_jsonl(run_dir / "raw" / "rejected_windows.jsonl", {"timestamp_utc": utc_now(), "label": label, "reason": "no_ovs_packets"})
                    continue
                if controller_table_size <= 0:
                    append_jsonl(run_dir / "raw" / "rejected_windows.jsonl", {"timestamp_utc": utc_now(), "label": label, "reason": "no_controller_flow_table"})
                    continue
                row = _record(
                    experiment_id,
                    label,
                    index,
                    source_host,
                    ovs,
                    packet_in,
                    cpu_pct,
                    tcp_delta.syn,
                    tcp_delta.ack,
                )
                # OVS uses short Linux bridge names; retain the stable,
                # descriptive identifier required by the dataset contract.
                row["switch_id"] = switch_name
                row["flow_table_size"] = controller_table_size
                store.append(row)
                completed[label] = index + 1
                # Disk shards, not in-memory buffers, are the resume boundary.
                # Updating only after each atomic shard keeps Drive responsive
                # during a multi-hour Colab capture.
                if completed[label] % args.shard_size == 0:
                    store.write_manifest(completed_counts=dict(store.completed_counts()), last_row=row["scenario_id"])
        store.flush_all()
        store.write_manifest(completed_counts=dict(store.completed_counts()), completed_utc=utc_now(), status="captured")
    finally:
        if background is not None and background.poll() is None:
            background.terminate()
        if tcp_counter is not None:
            tcp_counter.stop()
        if network is not None:
            network.stop()
        stop_process(controller)
