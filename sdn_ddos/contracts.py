"""Canonical dataset contract shared by capture, validation, and notebooks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


SCHEMA_VERSION: Final = "sdn-ddos-telemetry.v1"
WINDOW_SECONDS: Final = 1.0
DATA_SOURCE: Final = "mininet_ovs_ryu_measured"
LAB_NETWORK_CIDR: Final = "10.77.0.0/16"

DATASET_COLUMNS: Final[tuple[str, ...]] = (
    "timestamp_utc",
    "experiment_id",
    "scenario_id",
    "switch_id",
    "src_host",
    "dst_host",
    "protocol",
    "application",
    "window_seconds",
    "packet_count",
    "byte_count",
    "flow_count",
    "packet_rate",
    "byte_rate",
    "flow_rate",
    "mean_packet_size",
    "tcp_syn_count",
    "tcp_ack_count",
    "tcp_handshake_completion_ratio",
    "flow_table_size",
    "packet_in_count",
    "controller_cpu_proxy_pct",
    "attack_intensity",
    "attacker_count",
    "background_traffic_level",
    "label",
    "attack_family",
    "data_source",
)


@dataclass(frozen=True)
class Scenario:
    """Safe, local workload definition and its ground-truth label metadata."""

    label: str
    family: str
    protocol: str
    application: str
    intensity: float
    attackers: int
    background: float
    description: str


SCENARIOS: Final[tuple[Scenario, ...]] = (
    Scenario("BENIGN", "BENIGN", "TCP", "HTTP", 0.00, 0, 0.25, "Bounded browser-like HTTP and TCP traffic."),
    Scenario("UDP_FLOOD", "VOLUMETRIC", "UDP", "IPERF3", 0.75, 4, 0.20, "Bounded UDP throughput workload to an internal service."),
    Scenario("ICMP_FLOOD", "VOLUMETRIC", "ICMP", "PING", 0.70, 4, 0.20, "Bounded ICMP echo workload inside Mininet."),
    Scenario("UDP_AMPLIFICATION_STYLE", "REFLECTION_STYLE", "UDP", "IPERF3", 0.80, 4, 0.15, "Local high-rate UDP fan-in workload; no reflection or spoofing."),
    Scenario("SYN_FLOOD", "TRANSPORT", "TCP", "TCP_CONNECT", 0.80, 6, 0.15, "Many valid short local TCP connection attempts."),
    Scenario("PING_OF_DEATH_STYLE", "PROTOCOL_STYLE", "ICMP", "PING", 0.55, 3, 0.20, "High-rate valid MTU-safe ICMP workload; no malformed packets."),
    Scenario("SMURF_STYLE", "PROTOCOL_STYLE", "ICMP", "PING", 0.65, 4, 0.15, "High-rate unicast ICMP fan-in workload; no broadcast or spoofing."),
    Scenario("HTTP_FLOOD", "APPLICATION", "TCP", "HTTP", 0.75, 5, 0.20, "Bounded concurrent HTTP request workload to the internal web service."),
    Scenario("SLOWLORIS_STYLE", "APPLICATION", "TCP", "HTTP", 0.50, 4, 0.25, "Slow, valid local TCP request workload with connection limits."),
    Scenario("LAND_STYLE", "PROTOCOL_STYLE", "TCP", "TCP_CONNECT", 0.45, 3, 0.25, "Small valid local TCP workload; no source-address spoofing."),
    Scenario("PACKET_IN_FLOOD_STYLE", "SDN_CONTROL", "TCP", "TCP_CONNECT", 0.70, 6, 0.10, "High churn of valid local connections to exercise Packet-In handling."),
)

LABELS: Final[tuple[str, ...]] = tuple(scenario.label for scenario in SCENARIOS)
SCENARIO_BY_LABEL: Final[dict[str, Scenario]] = {scenario.label: scenario for scenario in SCENARIOS}

NUMERIC_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "window_seconds",
        "packet_count",
        "byte_count",
        "flow_count",
        "packet_rate",
        "byte_rate",
        "flow_rate",
        "mean_packet_size",
        "tcp_syn_count",
        "tcp_ack_count",
        "tcp_handshake_completion_ratio",
        "flow_table_size",
        "packet_in_count",
        "controller_cpu_proxy_pct",
        "attack_intensity",
        "attacker_count",
        "background_traffic_level",
    }
)


def scenario_for(label: str) -> Scenario:
    """Return a scenario or fail immediately on an unsupported label."""

    try:
        return SCENARIO_BY_LABEL[label]
    except KeyError as error:
        raise ValueError(f"Unsupported label: {label}") from error
