"""Validate a captured Mininet CSV and produce canonical Parquet/metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .schema import LABELS, REQUIRED_COLUMNS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rows-per-class", type=int, default=10_000)
    arguments = parser.parse_args()

    frame = pd.read_csv(arguments.input)
    if list(frame.columns) != REQUIRED_COLUMNS:
        raise ValueError("Capture schema differs from the required 28-column contract")
    expected_labels = LABELS
    counts = frame["label"].value_counts().sort_index()
    expected_counts = {label: arguments.rows_per_class for label in expected_labels}
    if counts.to_dict() != expected_counts:
        raise ValueError(f"Class balance failed: expected {expected_counts}, got {counts.to_dict()}")
    numeric_columns = [
        "window_seconds", "packet_count", "byte_count", "flow_count", "packet_rate",
        "byte_rate", "flow_rate", "mean_packet_size", "tcp_syn_count", "tcp_ack_count",
        "tcp_handshake_completion_ratio", "flow_table_size", "packet_in_count",
        "controller_cpu_proxy_pct", "attack_intensity", "attacker_count",
        "background_traffic_level",
    ]
    if frame[numeric_columns].isna().any().any() or (frame[numeric_columns] < 0).any().any():
        raise ValueError("Capture contains invalid numeric values")

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(arguments.output, index=False)
    frame.to_csv(arguments.output.with_suffix(".csv"), index=False)
    arguments.output.with_suffix(".json").write_text(json.dumps({
        "rows": int(len(frame)), "columns": int(len(frame.columns)),
        "labels": expected_labels, "rows_per_class": arguments.rows_per_class,
        "data_source": "mininet_ovs_counter_capture",
        "raw_capture": str(arguments.input),
        "limitations": "OVS counters are observed values. Controller-only metrics are zero because Ryu is unavailable on the installed Python 3.14 runtime.",
    }, indent=2), encoding="utf-8")
    print(f"Validated and wrote {len(frame):,} rows, {len(frame.columns)} columns to {arguments.output}")


if __name__ == "__main__":
    main()
