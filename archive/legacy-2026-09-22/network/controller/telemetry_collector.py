"""Read and validate raw JSONL telemetry emitted by the Ryu controller."""

import json
from pathlib import Path


def read_raw_telemetry(path):
    """Return raw records while rejecting malformed or incomplete JSON lines."""
    records = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid telemetry JSON at line {line_number}") from error
        required = {"timestamp_utc", "record_type", "switch_id"}
        if not required.issubset(record):
            raise ValueError(f"Missing telemetry fields at line {line_number}")
        records.append(record)
    return records