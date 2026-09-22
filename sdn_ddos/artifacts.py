"""Atomic, resumable telemetry artifacts without pandas or numpy."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable, Iterator, Mapping

from .contracts import DATASET_COLUMNS, LABELS, SCHEMA_VERSION


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Replace a JSON file atomically so a restart never sees half a manifest."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary_path = Path(handle.name)
    os.replace(temporary_path, path)


def append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")


def iter_csv_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def iter_shard_rows(run_dir: Path) -> Iterator[dict[str, str]]:
    for label in LABELS:
        shard_dir = run_dir / "shards" / label
        for shard in sorted(shard_dir.glob("part-*.csv")):
            yield from iter_csv_rows(shard)


class ShardStore:
    """Stores class-balanced rows in atomic CSV shards and records run state."""

    def __init__(self, run_dir: Path, experiment_id: str, shard_size: int = 250) -> None:
        if shard_size < 1:
            raise ValueError("shard_size must be positive")
        self.run_dir = run_dir
        self.experiment_id = experiment_id
        self.shard_size = shard_size
        self._buffers: dict[str, list[dict[str, Any]]] = {label: [] for label in LABELS}
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "shards").mkdir(exist_ok=True)

    @property
    def manifest_path(self) -> Path:
        return self.run_dir / "run_manifest.json"

    def completed_counts(self) -> Counter[str]:
        counts: Counter[str] = Counter()
        for row in iter_shard_rows(self.run_dir):
            counts[row["label"]] += 1
        return counts

    def write_manifest(self, **updates: Any) -> None:
        existing: dict[str, Any] = {}
        if self.manifest_path.exists():
            existing = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        existing.update(
            {
                "schema_version": SCHEMA_VERSION,
                "experiment_id": self.experiment_id,
                "updated_utc": utc_now(),
                **updates,
            }
        )
        atomic_json(self.manifest_path, existing)

    def append(self, row: Mapping[str, Any]) -> None:
        missing = set(DATASET_COLUMNS) - set(row)
        extra = set(row) - set(DATASET_COLUMNS)
        if missing or extra:
            raise ValueError(f"Row schema mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
        label = str(row["label"])
        if label not in LABELS:
            raise ValueError(f"Unsupported row label: {label}")
        self._buffers[label].append({column: row[column] for column in DATASET_COLUMNS})
        if len(self._buffers[label]) >= self.shard_size:
            self.flush(label)

    def flush(self, label: str) -> None:
        buffer = self._buffers[label]
        if not buffer:
            return
        shard_dir = self.run_dir / "shards" / label
        shard_dir.mkdir(parents=True, exist_ok=True)
        shard_number = len(list(shard_dir.glob("part-*.csv"))) + 1
        final_path = shard_dir / f"part-{shard_number:06d}.csv"
        with NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=shard_dir) as handle:
            writer = csv.DictWriter(handle, fieldnames=DATASET_COLUMNS)
            writer.writeheader()
            writer.writerows(buffer)
            temporary_path = Path(handle.name)
        os.replace(temporary_path, final_path)
        self._buffers[label] = []

    def flush_all(self) -> None:
        for label in LABELS:
            self.flush(label)


def combine_csv(run_dir: Path, output_path: Path) -> int:
    """Create one canonical CSV from shards with a stable, contractual header."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=output_path.parent) as handle:
        writer = csv.DictWriter(handle, fieldnames=DATASET_COLUMNS)
        writer.writeheader()
        count = 0
        for row in iter_shard_rows(run_dir):
            writer.writerow({column: row[column] for column in DATASET_COLUMNS})
            count += 1
        temporary_path = Path(handle.name)
    os.replace(temporary_path, output_path)
    return count


def write_parquet_from_csv(csv_path: Path, parquet_path: Path) -> None:
    """Write Parquet in bounded batches without converting data through pandas."""

    try:
        import pyarrow as pa
        import pyarrow.csv as pacsv
        import pyarrow.parquet as pq
    except ImportError as error:
        raise RuntimeError("Parquet output requires pyarrow. Install requirements-lab.txt.") from error

    table = pacsv.read_csv(csv_path, convert_options=pacsv.ConvertOptions(strings_can_be_null=False))
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = parquet_path.with_suffix(".tmp.parquet")
    pq.write_table(table, temporary_path, compression="zstd")
    os.replace(temporary_path, parquet_path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
