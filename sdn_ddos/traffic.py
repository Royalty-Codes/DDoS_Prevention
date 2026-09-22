"""Bounded, local-only traffic workloads for the Mininet laboratory."""

from __future__ import annotations

import ipaddress
import time
from dataclasses import dataclass, field
from typing import Any

from .contracts import LAB_NETWORK_CIDR, Scenario
from .topology import mininet_switch_name


def assert_lab_target(address: str) -> None:
    """Block traffic commands unless the target belongs to the private lab CIDR."""

    network = ipaddress.ip_network(LAB_NETWORK_CIDR)
    if ipaddress.ip_address(address) not in network:
        raise ValueError(f"Refusing non-lab traffic target: {address}")


def source_names(scenario: Scenario, sample_index: int) -> list[str]:
    if scenario.label == "BENIGN":
        pool = ("c1", "c2", "c3", "c4", "b1", "b2", "b3", "b4")
        return [pool[sample_index % len(pool)]]
    pool = ("a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8")
    return [pool[(sample_index + offset) % len(pool)] for offset in range(scenario.attackers)]


@dataclass
class TrafficSession:
    """Owns short-lived processes and guarantees they are stopped after a window."""

    processes: list[Any] = field(default_factory=list)

    def stop(self) -> None:
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
        deadline = time.monotonic() + 0.4
        for process in self.processes:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except Exception:
                if process.poll() is None:
                    process.kill()


class LocalTrafficRunner:
    """Starts safe workload shapes only against hosts inside the Mininet lab."""

    def __init__(self, network: Any, target_name: str = "web") -> None:
        self.network = network
        self.target = network.get(target_name)
        self.target_ip = self.target.IP()
        assert_lab_target(self.target_ip)

    def start_services(self) -> None:
        self.target.cmd("pkill -f 'http.server 8080' 2>/dev/null || true")
        self.target.cmd("pkill -f 'iperf3 -s' 2>/dev/null || true")
        self.target.cmd("python3 -m http.server 8080 --directory /tmp >/tmp/sdn-web.log 2>&1 &")
        self.target.cmd("iperf3 -s >/tmp/sdn-iperf.log 2>&1 &")

    def start_background(self) -> Any:
        client = self.network.get("c1")
        command = f"while true; do curl -fsS --max-time 0.5 http://{self.target_ip}:8080/ >/dev/null 2>&1 || true; sleep 0.2; done"
        return client.popen(["bash", "-lc", command])

    def start(self, scenario: Scenario, sample_index: int) -> tuple[TrafficSession, str]:
        names = source_names(scenario, sample_index)
        if scenario.label == "PACKET_IN_FLOOD_STYLE":
            # Remove only short-lived learning entries. The priority-0 table
            # miss remains, so the following valid connections create genuine
            # Ryu Packet-In events without spoofing or malformed traffic.
            switch_name = mininet_switch_name("leaf-red")
            self.network.get(switch_name).cmd(f"ovs-ofctl -O OpenFlow13 del-flows {switch_name} 'priority=10'")
        session = TrafficSession()
        for source_name in names:
            source = self.network.get(source_name)
            session.processes.append(source.popen(self._command(scenario)))
        return session, names[0]

    def _command(self, scenario: Scenario) -> list[str]:
        target = self.target_ip
        if scenario.label in {"BENIGN", "HTTP_FLOOD"}:
            iterations = 4 if scenario.label == "BENIGN" else 30
            return ["bash", "-lc", f"for i in $(seq 1 {iterations}); do curl -fsS --max-time 0.7 http://{target}:8080/ >/dev/null || true; done"]
        if scenario.label in {"UDP_FLOOD", "UDP_AMPLIFICATION_STYLE"}:
            rate = "4M" if scenario.label == "UDP_FLOOD" else "6M"
            return ["iperf3", "-c", target, "-u", "-b", rate, "-t", "1"]
        if scenario.label in {"ICMP_FLOOD", "SMURF_STYLE", "PING_OF_DEATH_STYLE"}:
            size = "1400" if scenario.label == "PING_OF_DEATH_STYLE" else "512"
            count = "20" if scenario.label == "ICMP_FLOOD" else "10"
            return ["ping", "-n", "-i", "0.04", "-s", size, "-c", count, target]
        if scenario.label == "SLOWLORIS_STYLE":
            return ["bash", "-lc", f"for i in $(seq 1 4); do (printf 'GET / HTTP/1.1\\r\\nHost: local\\r\\n'; sleep 0.5) | nc -w 1 {target} 8080 || true; done"]
        attempts = "60" if scenario.label == "PACKET_IN_FLOOD_STYLE" else "20"
        return ["bash", "-lc", f"for i in $(seq 1 {attempts}); do timeout 0.2 bash -c '</dev/tcp/{target}/8080' || true; done"]
