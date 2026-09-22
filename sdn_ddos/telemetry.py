"""Measured Open vSwitch and Ryu telemetry adapters.

The capture layer reads counter deltas from OVS and controller snapshots from a
Ryu JSONL journal. It deliberately has no Mininet import so schema and quality
tests run on Windows as well as Linux.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


_FLOW_COUNTER = re.compile(r"n_packets=(?P<packets>\d+),\s*n_bytes=(?P<bytes>\d+)")


class SwitchCommandRunner(Protocol):
    name: str

    def cmd(self, command: str) -> str: ...


@dataclass(frozen=True)
class OvsSnapshot:
    switch_id: str
    packet_total: int
    byte_total: int
    flow_table_size: int


@dataclass(frozen=True)
class OvsDelta:
    switch_id: str
    packet_count: int
    byte_count: int
    flow_count: int
    flow_table_size: int


def parse_ovs_flow_dump(switch_id: str, output: str) -> OvsSnapshot:
    """Parse OVS's measured flow counters from `ovs-ofctl dump-flows` output."""

    packet_total = 0
    byte_total = 0
    flow_table_size = 0
    for line in output.splitlines():
        match = _FLOW_COUNTER.search(line)
        if not match:
            continue
        packet_total += int(match.group("packets"))
        byte_total += int(match.group("bytes"))
        flow_table_size += 1
    return OvsSnapshot(switch_id, packet_total, byte_total, flow_table_size)


class OvsCounterCollector:
    """Converts monotonically increasing OVS counters into per-window deltas."""

    def __init__(self) -> None:
        self._previous: dict[str, OvsSnapshot] = {}

    def sample(self, switch: SwitchCommandRunner) -> OvsDelta:
        raw = switch.cmd(f"ovs-ofctl -O OpenFlow13 dump-flows {switch.name}")
        current = parse_ovs_flow_dump(switch.name, raw)
        previous = self._previous.get(switch.name)
        self._previous[switch.name] = current
        if previous is None:
            return OvsDelta(current.switch_id, 0, 0, 0, current.flow_table_size)
        # A switch reconnect/reset restarts counters. Treat its current value as
        # the new interval instead of creating negative observations.
        packets = current.packet_total - previous.packet_total
        bytes_ = current.byte_total - previous.byte_total
        flows = current.flow_table_size - previous.flow_table_size
        return OvsDelta(
            current.switch_id,
            packets if packets >= 0 else current.packet_total,
            bytes_ if bytes_ >= 0 else current.byte_total,
            flows if flows >= 0 else current.flow_table_size,
            current.flow_table_size,
        )


class ControllerJournal:
    """Reads the most recent valid controller snapshot for each OVS bridge."""

    def __init__(self, journal_path: Path) -> None:
        self.journal_path = journal_path
        self._last_packet_in_total: dict[str, int] = {}
        self._latest_by_switch: dict[str, dict[str, Any]] = {}
        self._offset = 0

    def latest(self, switch_id: str) -> dict[str, Any] | None:
        if not self.journal_path.exists():
            return None
        # The journal can grow for many hours. Tail only new bytes instead of
        # rereading every controller reply for every one-second capture window.
        if self.journal_path.stat().st_size < self._offset:
            self._offset = 0
            self._latest_by_switch.clear()
        with self.journal_path.open("r", encoding="utf-8") as handle:
            handle.seek(self._offset)
            for line in handle:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if item.get("event_type") == "flow_snapshot":
                    self._latest_by_switch[str(item.get("switch_id"))] = item
            self._offset = handle.tell()
        return self._latest_by_switch.get(switch_id)

    def interval(self, switch_id: str) -> tuple[int, float, int]:
        snapshot = self.latest(switch_id)
        if snapshot is None:
            raise RuntimeError(f"No Ryu flow snapshot is available for {switch_id}")
        packet_in_total = int(snapshot["packet_in_total"])
        previous = self._last_packet_in_total.get(switch_id, packet_in_total)
        self._last_packet_in_total[switch_id] = packet_in_total
        packet_in_delta = packet_in_total - previous
        if packet_in_delta < 0:
            packet_in_delta = packet_in_total
        return packet_in_delta, float(snapshot["controller_cpu_pct"]), int(snapshot["flow_table_size"])
