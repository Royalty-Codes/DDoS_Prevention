"""Normalizes Ryu flow-stat replies to JSON Lines for dataset building."""
import json
from datetime import datetime, timezone
def write_snapshot(path, datapath_id, flows):
    record = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'switch_id': str(datapath_id), 'flows': flows}
    with open(path, 'a', encoding='utf-8') as handle: handle.write(json.dumps(record) + '\n')
