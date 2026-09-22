"""Create a reproducible controlled SDN telemetry dataset for ML experiments.

Records are synthetic per-window profiles for an isolated Mininet/OVS/Ryu lab,
not packet captures or measurements of Internet traffic.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .scenarios import LABELS, SCENARIOS


def _bounded(value, low, high):
    return float(np.clip(value, low, high))


def _log_uniform(rng, low, high):
    return float(np.exp(rng.uniform(np.log(low), np.log(high))))


def generate(rows_per_class=3000, seed=42, window_seconds=10):
    """Generate balanced profiles with temporal, flow, and SDN telemetry context."""
    rng = np.random.default_rng(seed)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = []
    sites, services = ("campus", "branch", "edge", "research"), ("web", "dns", "ntp", "ssdp")
    for scenario_index, scenario in enumerate(SCENARIOS):
        benign = scenario["label"] == "BENIGN"
        tcp, udp = scenario["protocol"] in {"TCP", "MIXED"}, scenario["protocol"] in {"UDP", "MIXED"}
        for row_index in range(rows_per_class):
            sequence = scenario_index * rows_per_class + row_index
            timestamp = start + timedelta(seconds=sequence * window_seconds)
            background = float(rng.beta(2.3, 4.0))
            diurnal = .80 + .35 * np.sin((timestamp.hour * 60 + timestamp.minute) / 1440 * 2 * np.pi)
            intensity = _bounded(scenario["intensity"] * rng.normal(1, .12), 0, 1)
            pps = _log_uniform(rng, *scenario["pps"]) * diurnal * (.80 + .40 * background)
            if not benign and rng.random() < .08:  # deliberately overlap benign/low-rate windows
                pps *= rng.uniform(.35, .65)
            packets = max(1, int(pps * window_seconds * rng.lognormal(0, .11)))
            mean_size = _bounded(rng.normal(np.mean(scenario["packet_size"]), np.ptp(scenario["packet_size"]) / 5), 40, 1514)
            flows = max(1, int(_log_uniform(rng, *scenario["flows"]) * (.75 + background)))
            attackers = 0 if benign else int(rng.integers(1, 8))
            unique_src = max(1, int(flows * (rng.uniform(.10, .55) if benign else rng.uniform(.03, .35))))
            unique_dst = int(rng.integers(1, 7 if benign else 5))
            syn_ratio = rng.uniform(*scenario["syn_ratio"]) if tcp else 0
            ack_ratio = rng.uniform(*scenario["ack_ratio"]) if tcp else 0
            syn, ack = int(packets * syn_ratio), int(packets * ack_ratio)
            rst = int(packets * (rng.uniform(.01, .12) if tcp and "RST" in scenario["label"] else rng.uniform(0, .025))) if tcp else 0
            flow_rate, new_flow_rate = flows / window_seconds, flows / window_seconds * rng.uniform(.45, 1.4)
            packet_in = max(0, int(flows * rng.uniform(.25, 2.8) * (1 + .8 * intensity)))
            table_size, table_capacity = max(flows, int(flows * rng.uniform(1.2, 4.2) * (1 + background))), int(rng.choice([1000, 1500, 2000]))
            table_occupancy = _bounded(table_size / table_capacity, 0, 1)
            packet_rate, byte_rate = packets / window_seconds, packets / window_seconds * mean_size
            control_latency = _bounded(2.5 + 28 * table_occupancy + packet_in / 22 + rng.normal(0, 2), 1, 250)
            controller_cpu = _bounded(4 + 45 * table_occupancy + packet_in / 14 + 18 * intensity + rng.normal(0, 3), 1, 100)
            queue_occupancy = _bounded(.04 + .58 * packet_rate / (packet_rate + 900) + .18 * background + rng.normal(0, .05), 0, 1)
            drop_rate = _bounded(max(0, queue_occupancy - .50) * rng.uniform(.04, .25) + intensity * .012, 0, .55)
            records.append({
                "timestamp_utc": timestamp.isoformat(), "experiment_id": "controlled_sdn_lab_v3", "window_id": f"v3_{scenario_index:02d}_{row_index:06d}", "window_sequence": sequence,
                "site_id": rng.choice(sites), "switch_id": f"s{rng.integers(1, 7)}", "ingress_port": int(rng.integers(1, 9)), "egress_port": int(rng.integers(1, 9)),
                "src_host": f"{'c' if benign else 'a'}{rng.integers(1, 25)}", "dst_host": rng.choice(services), "protocol": scenario["protocol"], "application": scenario["application"],
                "window_seconds": window_seconds, "day_of_week": timestamp.weekday(), "hour_of_day": timestamp.hour, "packet_count": packets, "byte_count": int(packets * mean_size), "flow_count": flows,
                "packet_rate": packet_rate, "byte_rate": byte_rate, "flow_rate": flow_rate, "mean_packet_size": mean_size, "packet_size_std": _bounded(mean_size * rng.uniform(.08, .65), 4, 700),
                "inter_arrival_mean_ms": _bounded(1000 / max(packet_rate, .1), .02, 10000), "inter_arrival_std_ms": _bounded(1000 / max(packet_rate, .1) * rng.uniform(.25, 2.2), .01, 15000),
                "packet_rate_cv": _bounded(rng.normal(.30 + .55 * intensity, .16), .03, 2.5), "flow_duration_mean_s": _bounded(rng.lognormal(1.8 - .9 * intensity, .65), .05, 600), "flow_duration_std_s": _bounded(rng.lognormal(1.4 - .4 * intensity, .70), .02, 800),
                "new_flow_rate": new_flow_rate, "active_flow_ratio": _bounded(rng.normal(.35 + .42 * intensity, .16), .02, 1), "unique_src_count": unique_src, "unique_dst_count": unique_dst,
                "src_ip_entropy": _bounded(np.log2(unique_src) * rng.uniform(.62, 1), 0, 8), "dst_ip_entropy": _bounded(np.log2(unique_dst) * rng.uniform(.55, 1), 0, 5), "src_port_entropy": _bounded(rng.normal(2.8 + 2.2 * intensity, .7), .1, 8), "protocol_entropy": _bounded(rng.normal(.12 if scenario["protocol"] != "MIXED" else 1.1, .09), 0, 2),
                "tcp_syn_count": syn, "tcp_ack_count": ack, "tcp_rst_count": rst, "tcp_syn_ratio": syn / packets, "tcp_ack_ratio": ack / packets, "tcp_rst_ratio": rst / packets, "tcp_handshake_completion_ratio": _bounded(ack / max(syn, 1), 0, 2), "tcp_retransmission_ratio": _bounded(rng.normal(.012 + .10 * intensity, .025), 0, .5) if tcp else 0., "udp_fragmentation_ratio": _bounded(rng.normal(.01 + .08 * intensity, .025), 0, .5) if udp else 0.,
                "flow_table_size": table_size, "flow_table_capacity": table_capacity, "flow_table_occupancy": table_occupancy, "flow_table_change_rate": _bounded(new_flow_rate * rng.uniform(.4, 1.5), 0, 500), "packet_in_count": packet_in, "packet_in_rate": packet_in / window_seconds, "controller_cpu_proxy_pct": controller_cpu, "controller_latency_ms": control_latency, "queue_occupancy_ratio": queue_occupancy, "link_utilization_ratio": _bounded(byte_rate / 125_000_000, 0, 1), "dropped_packet_rate": drop_rate,
                "attack_intensity": intensity, "attacker_count": attackers, "background_traffic_level": background, "label": scenario["label"], "attack_family": scenario["family"], "data_source": "controlled_synthetic_profile", "schema_version": "v3",
            })
    return pd.DataFrame(records)


def write_dataset(frame, output_prefix):
    prefix = Path(output_prefix); prefix.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(prefix.with_suffix(".parquet"), index=False); frame.to_csv(prefix.with_suffix(".csv"), index=False)
    metadata = {"rows": len(frame), "columns": len(frame.columns), "classes": len(LABELS), "rows_per_class": int(frame.label.value_counts().min()), "labels": LABELS, "data_source": "controlled_synthetic_profile", "schema_version": "v3", "limitations": "Synthetic controlled SDN telemetry profiles; not packet captures or live-network measurements."}
    prefix.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--rows-per-class", type=int, default=3000); parser.add_argument("--seed", type=int, default=42); parser.add_argument("--output", default="data/processed/sdn_ddos_versatile")
    args = parser.parse_args(); frame = generate(args.rows_per_class, args.seed); write_dataset(frame, args.output)
    counts = frame["label"].value_counts().sort_index()
    if counts.nunique() != 1 or set(counts.index) != set(LABELS): raise ValueError("Generated dataset is not balanced across all labels")
    if not frame.select_dtypes(include="number").replace([np.inf, -np.inf], np.nan).notna().all().all(): raise ValueError("Generated dataset contains non-finite numeric values")
    print(f"wrote {len(frame):,} rows, {len(frame.columns)} columns, {len(LABELS)} equal classes")


if __name__ == "__main__": main()
