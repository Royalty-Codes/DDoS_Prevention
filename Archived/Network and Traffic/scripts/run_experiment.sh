#!/usr/bin/env bash
set -euo pipefail
NET="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$NET${PYTHONPATH:+:$PYTHONPATH}"
cd "$NET"
python3 - <<'PY'
from pathlib import Path
import yaml
from traffic.scenarios import SCENARIOS
from traffic.traffic_generator import assert_local_mininet_target, describe_schedule
from dataset.dataset_builder import build_lab_dataset
from dataset.labeling import label_for_window
from dataset.schema import LABELS, REQUIRED_COLUMNS

cfg_path = Path('config/experiment.yaml')
cfg = yaml.safe_load(cfg_path.read_text())
traffic_cfg = yaml.safe_load(Path('traffic/traffic_config.yaml').read_text())
output = (cfg_path.parent / cfg['dataset_output']).resolve()

assert traffic_cfg['lab_network'] == '10.0.0.0/8'
assert traffic_cfg['external_targets_allowed'] is False
assert_local_mininet_target('10.0.0.4')

for scenario in SCENARIOS:
    label, family = label_for_window(scenario)
    assert label in LABELS
    assert scenario['pps'][1] <= traffic_cfg['max_packets_per_second']
    print(describe_schedule(scenario), '->', family)

print('schema columns:', len(REQUIRED_COLUMNS))
print('rows_per_scenario:', cfg['rows_per_scenario'], 'seed:', cfg['seed'])
result = build_lab_dataset(SCENARIOS, cfg['rows_per_scenario'], output, cfg['seed'])
print(f'Wrote {len(result):,} rows x {len(result.columns)} cols to {output}')
print(result['label'].value_counts().sort_index().to_string())
PY
