"""Small regression checks for leakage-sensitive numerical and inference contracts."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from bda.experiment import attack_score, partition, threshold_from_validation, transform_numeric
from bda.serving import Predictor


class ExperimentContracts(unittest.TestCase):
    def test_portable_transform_uses_saved_medians_and_handles_nonfinite_cells(self):
        frame = pd.DataFrame({'rate': [12., np.inf, np.nan], 'constant': [8., 8., 8.]})
        stats = {'features': ['rate', 'constant'], 'median': [10., 8.], 'mean': [10., 8.], 'std': [2., 0.]}
        np.testing.assert_allclose(transform_numeric(frame, stats), [[1, 0], [0, 0], [0, 0]])

    def test_threshold_is_selected_from_validation_under_false_alarm_constraint(self):
        truth = np.array([False, False, True, True])
        scores = np.array([.1, .6, .5, .8])
        strict = threshold_from_validation(truth, scores, max_false_alarm=0)
        loose = threshold_from_validation(truth, scores, max_false_alarm=.5)
        self.assertEqual(strict, .8)
        self.assertEqual(loose, .5)

    def test_svm_margin_is_kept_as_a_score(self):
        margin = np.array([[-2., 3.], [4., -1.]])
        np.testing.assert_array_equal(attack_score(None, margin, 0), [2., -4.])

    def test_inference_rejects_missing_required_columns(self):
        predictor = Predictor.__new__(Predictor)
        predictor.contract = {'features': ['packet_rate']}
        with self.assertRaisesRegex(ValueError, 'packet_rate'):
            predictor.predict(pd.DataFrame({'unrelated': [1]}))

    def test_partitions_are_disjoint_and_training_constants_are_removed(self):
        frame = pd.DataFrame({'window_id': [f'w{i:04}' for i in range(260)],
                              'label': np.repeat([f'class_{i}' for i in range(13)], 20),
                              'rate': np.arange(260, dtype=float), 'constant': 10.})
        with tempfile.TemporaryDirectory() as directory:
            parts, features, _ = partition(frame, ['rate', 'constant'], Path(directory))
        self.assertEqual(features, ['rate'])
        groups = [set(part.window_id) for part in parts.values()]
        self.assertFalse(groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])
        self.assertEqual(sum(map(len, groups)), len(frame))


if __name__ == '__main__':
    unittest.main()
