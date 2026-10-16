"""Independent reconciliation of persisted predictions, metrics and split counts."""
import json
from pathlib import Path
import numpy as np
import pandas as pd


def verify(run_dir):
    run = Path(run_dir)
    metrics = pd.read_csv(run / 'model_metrics.csv')
    split = pd.read_csv(run / 'split_manifest.csv')
    assert len(metrics) == 9 and metrics.model.nunique() == 9
    assert not split.window_id.duplicated().any()
    assert len(split) == 39000
    assert split.groupby(['split','label']).size().groupby(level=0).nunique().eq(1).all()
    labels = json.loads((run / 'feature_contract.json').read_text())['labels']
    for _, row in metrics.iterrows():
        table = pd.read_parquet(run / 'predictions' / (row.model.lower().replace(' ', '_') + '.parquet'))
        assert len(table) == 5850
        np.testing.assert_allclose((table.actual == table.predicted).mean(), row.accuracy, atol=1e-12)
        per_class_f1 = []
        for label in labels:
            tp = ((table.actual == label) & (table.predicted == label)).sum()
            fp = ((table.actual != label) & (table.predicted == label)).sum()
            fn = ((table.actual == label) & (table.predicted != label)).sum()
            per_class_f1.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0)
        np.testing.assert_allclose(np.mean(per_class_f1), row.f1_macro, atol=1e-12)
        actual_attack, predicted_attack = table.actual != 'BENIGN', table.predicted != 'BENIGN'
        assert int((~actual_attack & predicted_attack).sum()) == row.fp
        assert int((actual_attack & ~predicted_attack).sum()) == row.fn
    selection = json.loads((run / 'selection.json').read_text())
    expected = metrics.sort_values('validation_macro_f1', ascending=False).iloc[0].model
    assert selection['winner'] == expected
    return {'independent_metric_reconciliation': True, 'models': 9, 'test_predictions': 9 * 5850,
            'disjoint_manifest_rows': len(split)}


if __name__ == '__main__':
    import sys
    print(json.dumps(verify(sys.argv[1]), indent=2))
