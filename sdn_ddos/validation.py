"""Dataset-quality gates for the measured 28-column capture contract."""

from __future__ import annotations

import csv
import json
import math
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from .artifacts import combine_csv, sha256, utc_now, write_parquet_from_csv
from .contracts import DATASET_COLUMNS, DATA_SOURCE, LABELS, NUMERIC_COLUMNS, SCHEMA_VERSION, WINDOW_SECONDS


def _as_float(row: dict[str, str], column: str) -> float:
    try:
        value = float(row[column])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid numeric value for {column}: {row.get(column)!r}") from error
    if not math.isfinite(value):
        raise ValueError(f"Non-finite value for {column}: {value!r}")
    return value


def validate_rows(csv_path: Path, rows_per_class: int) -> dict[str, Any]:
    """Check schema, balance, value ranges, uniqueness, and measured telemetry."""

    counts: Counter[str] = Counter()
    scenario_ids: set[str] = set()
    switches: set[str] = set()
    nonzero = Counter()
    row_count = 0
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != DATASET_COLUMNS:
            raise ValueError("CSV header does not exactly match the canonical 28-column contract")
        for row in reader:
            row_count += 1
            label = row["label"]
            if label not in LABELS:
                raise ValueError(f"Unexpected label: {label}")
            if row["data_source"] != DATA_SOURCE:
                raise ValueError(f"Unexpected data source: {row['data_source']}")
            if row["scenario_id"] in scenario_ids:
                raise ValueError(f"Duplicate scenario_id: {row['scenario_id']}")
            scenario_ids.add(row["scenario_id"])
            counts[label] += 1
            switches.add(row["switch_id"])
            values = {column: _as_float(row, column) for column in NUMERIC_COLUMNS}
            if any(value < 0 for value in values.values()):
                raise ValueError(f"Negative measured/metadata value in {row['scenario_id']}")
            if abs(values["window_seconds"] - WINDOW_SECONDS) > 0.05:
                raise ValueError(f"Unexpected capture window: {values['window_seconds']}")
            if values["packet_count"] > 0:
                expected_rate = values["packet_count"] / values["window_seconds"]
                if not math.isclose(values["packet_rate"], expected_rate, rel_tol=0.02, abs_tol=1.0):
                    raise ValueError(f"packet_rate mismatch in {row['scenario_id']}")
            if values["byte_count"] > 0 and values["packet_count"] > 0:
                expected_size = values["byte_count"] / values["packet_count"]
                if not math.isclose(values["mean_packet_size"], expected_size, rel_tol=0.02, abs_tol=1.0):
                    raise ValueError(f"mean_packet_size mismatch in {row['scenario_id']}")
            for metric in ("packet_count", "flow_count", "flow_table_size", "packet_in_count", "controller_cpu_proxy_pct"):
                if values[metric] > 0:
                    nonzero[metric] += 1
    expected = {label: rows_per_class for label in LABELS}
    if dict(counts) != expected:
        raise ValueError(f"Class balance mismatch: expected={expected}, actual={dict(counts)}")
    for metric in ("packet_count", "flow_count", "flow_table_size", "packet_in_count", "controller_cpu_proxy_pct"):
        if nonzero[metric] == 0:
            raise ValueError(f"Measured telemetry metric is entirely zero: {metric}")
    if len(switches) < 3:
        raise ValueError("Capture did not exercise enough ingress switches")
    return {
        "validated_utc": utc_now(),
        "schema_version": SCHEMA_VERSION,
        "rows": row_count,
        "columns": len(DATASET_COLUMNS),
        "rows_per_class": rows_per_class,
        "labels": list(LABELS),
        "distinct_switches": sorted(switches),
        "nonzero_rows_by_metric": dict(nonzero),
        "csv_sha256": sha256(csv_path),
    }


def finalize_run(run_dir: Path, rows_per_class: int) -> dict[str, Any]:
    """Combine, validate, and then publish final artifacts.

    All work happens in a temporary sibling directory.  A failed quality gate
    therefore cannot be mistaken for a publishable dataset.
    """

    final_dir = run_dir / "final"
    csv_path = final_dir / "sdn_ddos_measured_28x11.csv"
    parquet_path = final_dir / "sdn_ddos_measured_28x11.parquet"
    report_path = final_dir / "validation_report.json"
    with tempfile.TemporaryDirectory(prefix=".final-staging-", dir=run_dir) as staging_name:
        staging_dir = Path(staging_name)
        staged_csv = staging_dir / csv_path.name
        staged_parquet = staging_dir / parquet_path.name
        staged_report = staging_dir / report_path.name
        combine_csv(run_dir, staged_csv)
        report = validate_rows(staged_csv, rows_per_class)
        write_parquet_from_csv(staged_csv, staged_parquet)
        final_dir.mkdir(parents=True, exist_ok=True)
        report["parquet_path"] = str(parquet_path)
        report["csv_path"] = str(csv_path)
        staged_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staged_csv.replace(csv_path)
        staged_parquet.replace(parquet_path)
        staged_report.replace(report_path)
    return report
