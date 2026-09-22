"""Capture labeled, local-only traffic measurements from Mininet and OVS.

This collector deliberately keeps the existing 28-column controlled-lab
contract.  Unlike the older NumPy/Pandas profile generator, packet, byte, and
flow-table values here are deltas of Open vSwitch counters observed in an
isolated Mininet namespace.

The scenario names are dataset labels, not instructions for attacking a real
network.  Every generated packet remains inside the 10.77.0.0/24 Mininet lab.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import select
import signal
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from mininet.link import TCLink
from mininet.net import Mininet
from mininet.node import OVSSwitch

from .schema import REQUIRED_COLUMNS


# All workloads are bounded and run only against the target Mininet namespace.
# The labels preserve the existing project taxonomy; "_STYLE" labels use safe
# traffic shapes rather than malformed packets, reflection, spoofing, or
# external targets.
SCENARIOS = [
    ("BENIGN", "BENIGN", "TCP", "HTTP", 2, "tcp", 2, 2.0),
    ("UDP_FLOOD", "VOLUMETRIC", "UDP", "UDP", 8, "udp", 18, 10.0),
    ("ICMP_FLOOD", "VOLUMETRIC", "ICMP", "ICMP", 8, "icmp", 0, 0.0),
    ("UDP_AMPLIFICATION_STYLE", "REFLECTION_AMPLIFICATION", "UDP", "UDP", 10, "udp", 28, 14.0),
    ("SYN_FLOOD", "PROTOCOL_TRANSPORT", "TCP", "TCP", 16, "tcp", 3, 1.5),
    ("PING_OF_DEATH_STYLE", "PROTOCOL_ANOMALY", "ICMP", "ICMP", 10, "icmp_large", 0, 0.0),
    ("SMURF_STYLE", "REFLECTION_AMPLIFICATION", "ICMP", "ICMP", 12, "icmp", 0, 0.0),
    ("HTTP_FLOOD", "APPLICATION_LAYER", "TCP", "HTTP", 12, "tcp", 7, 3.5),
    ("SLOWLORIS_STYLE", "APPLICATION_LAYER", "TCP", "HTTP", 14, "tcp", 1, 0.4),
    ("LAND_STYLE", "PROTOCOL_ANOMALY", "TCP", "TCP", 14, "tcp", 1, 0.6),
    ("PACKET_IN_FLOOD_STYLE", "CONTROL_PLANE", "TCP", "TCP", 20, "tcp", 2, 1.0),
]

FLOW_COUNTER_PATTERN = re.compile(
    r"n_packets=(?P<packets>\d+),\s*n_bytes=(?P<bytes>\d+).*?"
    r"nw_src=(?P<src>10\.77\.0\.\d+)(?:/\d+)?,nw_dst=(?P<dst>10\.77\.0\.254)"
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows-per-class", type=int, default=10_000)
    parser.add_argument("--sample-interval", type=float, default=0.25)
    parser.add_argument("--source-count", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def validate_arguments(arguments: argparse.Namespace) -> None:
    if arguments.rows_per_class < arguments.source_count:
        raise ValueError("rows-per-class must be at least source-count")
    if arguments.sample_interval < 0.15:
        raise ValueError("sample-interval must be at least 0.15 seconds")
    if arguments.source_count < 2:
        raise ValueError("source-count must be at least 2")


def build_lab(source_count: int) -> tuple[Mininet, list, object]:
    """Create one isolated OVS switch with local sources and one target."""
    network = Mininet(controller=None, switch=OVSSwitch, link=TCLink, build=False)
    switch = network.addSwitch("s1", protocols="OpenFlow13", failMode="standalone")
    sources = [
        network.addHost(f"a{index:02d}", ip=f"10.77.0.{index}/24")
        for index in range(1, source_count + 1)
    ]
    target = network.addHost("target", ip="10.77.0.254/24")
    for host in sources:
        network.addLink(host, switch, cls=TCLink, bw=100)
    network.addLink(target, switch, cls=TCLink, bw=100)
    network.build()
    network.start()

    for source in sources:
        source.setARP(target.IP(), target.MAC())
        target.setARP(source.IP(), source.MAC())
    install_measured_flow_rules(network, switch, sources, target)
    return network, sources, target


def install_measured_flow_rules(network: Mininet, switch, sources: list, target) -> None:
    """Install one measurable forward and reverse OpenFlow rule per host."""
    switch_name = switch.name
    switch.cmd(f"ovs-ofctl -O OpenFlow13 del-flows {switch_name}")
    target_port = switch.ports[switch_side_interface(target)]
    for source in sources:
        source_port = switch.ports[switch_side_interface(source)]
        forward = (
            f"priority=100,ip,in_port={source_port},nw_src={source.IP()},"
            f"nw_dst={target.IP()},actions=output:{target_port}"
        )
        reverse = (
            f"priority=100,ip,in_port={target_port},nw_src={target.IP()},"
            f"nw_dst={source.IP()},actions=output:{source_port}"
        )
        switch.cmd(f"ovs-ofctl -O OpenFlow13 add-flow {switch_name} '{forward}'")
        switch.cmd(f"ovs-ofctl -O OpenFlow13 add-flow {switch_name} '{reverse}'")


def switch_side_interface(host):
    """Return the switch endpoint of a host's sole Mininet link."""
    link = host.defaultIntf().link
    return link.intf2 if link.intf1.node is host else link.intf1


def read_forward_counters(switch, target_ip: str) -> dict[str, tuple[int, int]]:
    """Read cumulative OVS counters for source-to-target flow rules."""
    output = switch.cmd(f"ovs-ofctl -O OpenFlow13 dump-flows {switch.name}")
    counters: dict[str, tuple[int, int]] = {}
    for line in output.splitlines():
        match = FLOW_COUNTER_PATTERN.search(line.replace(" ", ""))
        if match is None or match.group("dst") != target_ip:
            continue
        counters[match.group("src")] = (int(match.group("packets")), int(match.group("bytes")))
    return counters


def read_flow_table_size(switch) -> int:
    output = switch.cmd(f"ovs-ofctl -O OpenFlow13 dump-flows {switch.name}")
    return sum("actions=" in line for line in output.splitlines())


def start_tcp_observer(target) -> tuple[subprocess.Popen, Counter, Counter]:
    """Observe TCP SYN/ACK flags at the target without inventing TCP metrics."""
    command = ["tcpdump", "-l", "-nn", "-i", target.defaultIntf().name, "tcp"]
    process = target.popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    if process.stdout is not None:
        os.set_blocking(process.stdout.fileno(), False)
    return process, Counter(), Counter()


def drain_tcp_observer(process: subprocess.Popen, syn_counts: Counter, ack_counts: Counter) -> None:
    """Non-blockingly accumulate TCP flags from tcpdump's line-buffered output."""
    if process.stdout is None:
        return
    descriptor = process.stdout.fileno()
    while True:
        ready, _, _ = select.select([descriptor], [], [], 0)
        if not ready:
            return
        try:
            line = process.stdout.readline()
        except BlockingIOError:
            return
        if not line:
            return
        source_match = re.search(r"(10\.77\.0\.\d+)\.\d+\s+>\s+10\.77\.0\.254", line)
        if source_match is None:
            continue
        source_ip = source_match.group(1)
        flags_match = re.search(r"Flags \[([^\]]+)\]", line)
        flags = flags_match.group(1) if flags_match else ""
        if "S" in flags:
            syn_counts[source_ip] += 1
        if "." in flags:
            ack_counts[source_ip] += 1


def start_traffic(sources: list, target, workload: str, parallel_streams: int, mbps: float):
    """Start only bounded, local Mininet processes for the selected shape."""
    processes = []
    target_ip = target.IP()
    if workload in {"tcp", "udp"}:
        if workload == "udp":
            server_code = "exec(" + repr(
                """import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("0.0.0.0", 9000))
while True:
    s.recvfrom(65535)
"""
            ) + ")"
        else:
            server_code = "exec(" + repr(
                """import socket
import threading

def handle(connection):
    while connection.recv(65535):
        pass
    connection.close()

server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", 9000))
server.listen(128)
while True:
    connection, _ = server.accept()
    threading.Thread(target=handle, args=(connection,), daemon=True).start()
"""
            ) + ")"
        processes.append(target.popen(
            ["python3", "-u", "-c", server_code],
            stdout=None,
            stderr=None,
        ))
        time.sleep(0.2)
        for source in sources:
            if workload == "udp":
                client_code = "exec(" + repr(
                    """import socket
import sys
import time

host = sys.argv[1]
rate = float(sys.argv[2])
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
payload = b"x" * 1400
delay = 1400 * 8 / (rate * 1_000_000)
end = time.time() + 3600
while time.time() < end:
    sock.sendto(payload, (host, 9000))
    time.sleep(delay)
"""
                ) + ")"
                command = ["python3", "-u", "-c", client_code, target_ip, str(mbps)]
            else:
                client_code = "exec(" + repr(
                    """import socket
import sys
import time

host = sys.argv[1]
mode = sys.argv[2]
end = time.time() + 3600
while time.time() < end:
    try:
        connection = socket.create_connection((host, 9000), timeout=1)
        if mode == "burst":
            connection.sendall(b"x" * 1400)
            connection.close()
        elif mode == "slow":
            connection.sendall(b"x")
            time.sleep(0.08)
            connection.close()
        else:
            connection.sendall(b"x" * 65535)
            time.sleep(0.01)
            connection.close()
    except OSError:
        pass
"""
                ) + ")"
                mode = "slow" if mbps < 1 else "burst" if parallel_streams > 5 else "stream"
                command = ["python3", "-u", "-c", client_code, target_ip, mode]
            processes.append(source.popen(command, stdout=None, stderr=None))
    else:
        payload_size = "1400" if workload == "icmp_large" else "56"
        interval = "0.02" if workload == "icmp" else "0.04"
        for source in sources:
            command = ["ping", "-n", "-i", interval, "-s", payload_size, target_ip]
            processes.append(source.popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    return processes


def stop_processes(processes: list, target) -> None:
    for process in processes:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()


def delta(current: int, previous: int) -> int:
    return max(current - previous, 0)


def capture_scenario(writer, network, switch, sources, target, scenario, rows_per_class: int, sample_interval: float) -> int:
    label, family, protocol, application, intensity, workload, streams, mbps = scenario
    previous_counters = read_forward_counters(switch, target.IP())
    previous_syn: Counter = Counter()
    previous_ack: Counter = Counter()
    observer, syn_counts, ack_counts = start_tcp_observer(target)
    processes = start_traffic(sources, target, workload, streams, mbps)
    written = 0
    sequence = 0
    try:
        time.sleep(1.0)
        while written < rows_per_class:
            before = time.monotonic()
            drain_tcp_observer(observer, syn_counts, ack_counts)
            current_counters = read_forward_counters(switch, target.IP())
            flow_table_size = read_flow_table_size(switch)
            elapsed = max(time.monotonic() - before, sample_interval)
            timestamp = datetime.now(timezone.utc).isoformat()
            for source in sources:
                source_ip = source.IP()
                packet_total, byte_total = current_counters.get(source_ip, (0, 0))
                prior_packets, prior_bytes = previous_counters.get(source_ip, (packet_total, byte_total))
                packets = delta(packet_total, prior_packets)
                bytes_ = delta(byte_total, prior_bytes)
                syn = delta(syn_counts[source_ip], previous_syn[source_ip])
                ack = delta(ack_counts[source_ip], previous_ack[source_ip])
                if packets <= 0:
                    continue
                writer.writerow({
                    "timestamp_utc": timestamp,
                    "experiment_id": "mininet_ovs_capture_v1",
                    "scenario_id": f"{label.lower()}_{sequence:06d}",
                    "switch_id": switch.name,
                    "src_host": source.name,
                    "dst_host": target.name,
                    "protocol": protocol,
                    "application": application,
                    "window_seconds": round(elapsed, 6),
                    "packet_count": packets,
                    "byte_count": bytes_,
                    "flow_count": 1,
                    "packet_rate": packets / elapsed,
                    "byte_rate": bytes_ / elapsed,
                    "flow_rate": 1 / elapsed,
                    "mean_packet_size": bytes_ / max(packets, 1),
                    "tcp_syn_count": syn,
                    "tcp_ack_count": ack,
                    "tcp_handshake_completion_ratio": ack / max(syn, 1),
                    "flow_table_size": flow_table_size,
                    "packet_in_count": 0,
                    "controller_cpu_proxy_pct": 0.0,
                    "attack_intensity": intensity,
                    "attacker_count": len(sources),
                    "background_traffic_level": 0.0,
                    "label": label,
                    "attack_family": family,
                    "data_source": "mininet_ovs_counter_capture",
                })
                written += 1
                if written >= rows_per_class:
                    break
            previous_counters = current_counters
            previous_syn = syn_counts.copy()
            previous_ack = ack_counts.copy()
            sequence += 1
            remaining = sample_interval - (time.monotonic() - before)
            if remaining > 0:
                time.sleep(remaining)
    finally:
        stop_processes(processes, target)
        observer.terminate()
        try:
            observer.wait(timeout=2)
        except subprocess.TimeoutExpired:
            observer.kill()
    return written


def main() -> None:
    arguments = parse_arguments()
    validate_arguments(arguments)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    network = None
    try:
        network, sources, target = build_lab(arguments.source_count)
        with arguments.output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
            writer.writeheader()
            rows_by_label = {}
            for scenario in SCENARIOS:
                label = scenario[0]
                rows_by_label[label] = capture_scenario(
                    writer, network, network.get("s1"), sources, target, scenario,
                    arguments.rows_per_class, arguments.sample_interval,
                )
                handle.flush()
                print(f"{label}: {rows_by_label[label]:,} captured rows", flush=True)
    finally:
        if network is not None:
            network.stop()

    metadata_path = arguments.output.with_suffix(".capture.json")
    metadata_path.write_text(json.dumps({
        "capture_type": "isolated Mininet/OVS counter capture",
        "rows_per_class_requested": arguments.rows_per_class,
        "labels": [scenario[0] for scenario in SCENARIOS],
        "columns": REQUIRED_COLUMNS,
        "controller_metrics": "No Ryu process was available on Python 3.14; packet_in_count and controller_cpu_proxy_pct are explicitly 0/unavailable.",
        "safety_boundary": "All traffic ran only in the 10.77.0.0/24 Mininet namespace.",
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
