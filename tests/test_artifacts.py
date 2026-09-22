from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sdn_ddos.artifacts import ShardStore, combine_csv, iter_shard_rows
from sdn_ddos.contracts import DATASET_COLUMNS, DATA_SOURCE, scenario_for
from sdn_ddos.validation import finalize_run


def row(label: str, index: int) -> dict[str, object]:
    scenario = scenario_for(label)
    values: dict[str, object] = {column: "" for column in DATASET_COLUMNS}
    values.update(
        {
            "timestamp_utc": "2026-01-01T00:00:00+00:00",
            "experiment_id": "test",
            "scenario_id": f"{label}-{index}",
            "switch_id": "leaf-campus",
            "src_host": "c1",
            "dst_host": "web",
            "protocol": scenario.protocol,
            "application": scenario.application,
            "window_seconds": 1.0,
            "packet_count": 10,
            "byte_count": 1000,
            "flow_count": 2,
            "packet_rate": 10.0,
            "byte_rate": 1000.0,
            "flow_rate": 2.0,
            "mean_packet_size": 100.0,
            "tcp_syn_count": 1,
            "tcp_ack_count": 1,
            "tcp_handshake_completion_ratio": 1.0,
            "flow_table_size": 5,
            "packet_in_count": 1,
            "controller_cpu_proxy_pct": 1.0,
            "attack_intensity": scenario.intensity,
            "attacker_count": scenario.attackers,
            "background_traffic_level": scenario.background,
            "label": label,
            "attack_family": scenario.family,
            "data_source": DATA_SOURCE,
        }
    )
    return values


class ArtifactTests(unittest.TestCase):
    def test_shards_are_written_and_combined_atomically(self) -> None:
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            store = ShardStore(tmp_path / "run", experiment_id="test", shard_size=2)
            store.append(row("BENIGN", 0))
            store.append(row("BENIGN", 1))
            store.flush_all()
            self.assertEqual(len(list(iter_shard_rows(tmp_path / "run"))), 2)
            output = tmp_path / "final.csv"
            self.assertEqual(combine_csv(tmp_path / "run", output), 2)
            self.assertEqual(output.read_text(encoding="utf-8").splitlines()[0].split(","), list(DATASET_COLUMNS))

    def test_failed_validation_does_not_publish_final_files(self) -> None:
        with TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run"
            store = ShardStore(run_dir, experiment_id="test", shard_size=1)
            store.append(row("BENIGN", 0))
            store.flush_all()
            with self.assertRaises(ValueError):
                finalize_run(run_dir, rows_per_class=1)
            self.assertFalse((run_dir / "final").exists())
