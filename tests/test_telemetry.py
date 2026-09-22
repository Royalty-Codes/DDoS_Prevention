import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sdn_ddos.telemetry import ControllerJournal, OvsCounterCollector, parse_ovs_flow_dump


class FakeSwitch:
    name = "leaf-campus"

    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)

    def cmd(self, command: str) -> str:
        return next(self.responses)


class TelemetryTests(unittest.TestCase):
    def test_parse_and_delta_use_measured_counters(self) -> None:
        first = "cookie=0x0, duration=1.0s, n_packets=10, n_bytes=1000, priority=10\n"
        second = "cookie=0x0, duration=2.0s, n_packets=25, n_bytes=2500, priority=10\n"
        snapshot = parse_ovs_flow_dump("leaf-campus", second)
        self.assertEqual(snapshot.packet_total, 25)
        self.assertEqual(snapshot.byte_total, 2500)
        self.assertEqual(snapshot.flow_table_size, 1)
        collector = OvsCounterCollector()
        switch = FakeSwitch([first, second])
        collector.sample(switch)
        delta = collector.sample(switch)
        self.assertEqual((delta.packet_count, delta.byte_count, delta.flow_count), (15, 1500, 0))

    def test_controller_journal_tails_only_new_snapshots(self) -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "controller.jsonl"
            path.write_text(
                '{"event_type":"flow_snapshot","switch_id":"1","packet_in_total":4,"controller_cpu_pct":2.5,"flow_table_size":6}\n',
                encoding="utf-8",
            )
            journal = ControllerJournal(path)
            self.assertEqual(journal.interval("1"), (0, 2.5, 6))
            with path.open("a", encoding="utf-8") as handle:
                handle.write('{"event_type":"flow_snapshot","switch_id":"1","packet_in_total":9,"controller_cpu_pct":3.0,"flow_table_size":8}\n')
            self.assertEqual(journal.interval("1"), (5, 3.0, 8))
