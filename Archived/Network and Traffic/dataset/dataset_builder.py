"""Builds a large Parquet dataset from repeated local lab windows."""
from datetime import datetime, timezone
from pathlib import Path
import json
import numpy as np
import pandas as pd
from .schema import REQUIRED_COLUMNS
from .labeling import label_for_window
from .feature_engineering import compute_window_features


def _bounded(rng, low, high):
    return float(rng.uniform(low, high))


def build_lab_dataset(scenarios, rows_per_scenario, output_path, seed=42):
    """Create reproducible local-lab telemetry-shaped records.

    Raw counters are sampled from the controlled scenario plan. Window rates
    and TCP ratios are derived with `compute_window_features`, and class names
    come from `label_for_window`. `data_source` distinguishes this fallback
    from captured OpenFlow telemetry.
    """
    rng = np.random.default_rng(seed)
    records = []
    for scenario_index, scenario in enumerate(scenarios):
        label, family = label_for_window(scenario)
        for row_index in range(rows_per_scenario):
            pps = _bounded(rng, *scenario['pps'])
            size = _bounded(rng, *scenario['packet_size'])
            flows = max(1, int(_bounded(rng, *scenario['flows'])))
            seconds = float(scenario['window_seconds'])
            packets = max(1, int(pps * seconds * _bounded(rng, .9, 1.1)))
            syn = int(packets * _bounded(rng, .55, .98)) if scenario['protocol'] == 'TCP' else 0
            ack = int(syn * _bounded(rng, *scenario['ack_ratio']))
            table = max(1, int(flows * _bounded(rng, 1, 3)))
            packet_in = max(0, int(flows * _bounded(rng, .1, 2)))
            previous = {
                'packets': 0, 'bytes': 0, 'flows': 0, 'syn': 0, 'ack': 0,
                'flow_table_size': 1, 'packet_in': 0,
            }
            current = {
                'packets': packets,
                'bytes': int(packets * size),
                'flows': flows,
                'syn': syn,
                'ack': ack,
                'flow_table_size': table,
                'packet_in': packet_in,
            }
            feats = compute_window_features(previous, current, seconds)
            record = {
                'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                'experiment_id': 'mininet_ryu_controlled_v1',
                'scenario_id': f"{label.lower()}_{scenario_index:02d}_{row_index:06d}",
                'switch_id': 's1',
                'src_host': f"h{int(rng.integers(1, 5))}",
                'dst_host': 'h4',
                'protocol': scenario['protocol'],
                'application': scenario['application'],
                **feats,
                'attack_intensity': scenario['attack_intensity'],
                'attacker_count': scenario['attacker_count'],
                'background_traffic_level': _bounded(rng, .1, .6),
                'label': label,
                'attack_family': family,
                'data_source': 'controlled_lab_profile',
            }
            record['controller_cpu_proxy_pct'] = min(
                100.0, _bounded(rng, *scenario['controller_proxy'])
            )
            records.append(record)
    frame = pd.DataFrame(records).reindex(columns=REQUIRED_COLUMNS)
    if frame.isna().any().any() or not (frame['packet_rate'] >= 0).all():
        raise ValueError('Dataset validation failed')
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(destination, index=False)
    destination.with_suffix('.json').write_text(json.dumps({
        'rows': len(frame),
        'columns': len(frame.columns),
        'labels': sorted(frame.label.unique()),
        'data_source': 'controlled_lab_profile',
        'note': 'Run the OpenFlow collector for data_source=real_openflow telemetry.',
    }, indent=2))
    return frame
