"""Load one persisted model and return offline, inspectable prediction records."""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .experiment import start_spark, transform_numeric


class Predictor:
    def __init__(self, run_dir):
        self.run_dir = Path(run_dir)
        selection = json.loads((self.run_dir / 'selection.json').read_text())
        self.name = selection['winner']
        self.engine = selection['models'][self.name]['engine']
        self.contract = json.loads((self.run_dir / 'feature_contract.json').read_text())
        self.stats = json.loads((self.run_dir / 'preprocessing.json').read_text())
        self.environment = json.loads((self.run_dir / 'environment.json').read_text())
        self.operation = json.loads((self.run_dir / 'operating_points.json').read_text())[self.name]
        self.spark = None
        slug = self.name.lower().replace(' ', '_')
        if self.engine == 'Spark':
            from pyspark.ml.classification import (
                DecisionTreeClassificationModel, LogisticRegressionModel,
                MultilayerPerceptronClassificationModel, NaiveBayesModel,
                RandomForestClassificationModel,
            )
            classes = {'Decision Tree': DecisionTreeClassificationModel,
                       'Logistic Regression': LogisticRegressionModel,
                       'Multilayer Perceptron': MultilayerPerceptronClassificationModel,
                       'Gaussian Naive Bayes': NaiveBayesModel,
                       'Random Forest': RandomForestClassificationModel}
            self.spark, _ = start_spark()
            self.model = classes[self.name].load(str(self.run_dir / 'models' / (slug + '.spark')))
        else:
            self.model = joblib.load(self.run_dir / 'models' / (slug + '.joblib'))

    def predict(self, windows):
        absent = sorted(set(self.contract['features']) - set(windows.columns))
        if absent:
            raise ValueError(f'Missing required telemetry columns: {absent}')
        if not len(windows):
            return pd.DataFrame()
        values = transform_numeric(windows, self.stats)
        benign = self.contract['labels'].index('BENIGN')
        if self.engine == 'Spark':
            from pyspark.ml.linalg import Vectors
            batch = self.spark.createDataFrame([(i, Vectors.dense(row)) for i, row in enumerate(values)],
                                               ['row_id', 'features'])
            output = self.model.transform(batch).select('row_id', 'prediction', 'probability').toPandas().sort_values('row_id')
            predicted = output.prediction.to_numpy(dtype=int)
            probabilities = np.vstack([v.toArray() for v in output.probability])
            score = 1 - probabilities[:, benign]
        else:
            predicted = self.model.predict(values)
            if hasattr(self.model, 'predict_proba'):
                probabilities = self.model.predict_proba(values)
                score = 1 - probabilities[:, benign]
            else:
                probabilities = None
                score = -self.model.decision_function(values)[:, benign]
        result = pd.DataFrame({'predicted_class': np.asarray(self.contract['labels'])[predicted],
                               'attack_score': score, 'score_type': self.operation['score_kind'],
                               'threshold': self.operation['threshold'],
                               'attack_alert': score >= self.operation['threshold'],
                               'model': self.name, 'training_commit': self.environment['git_commit'],
                               'scope': 'offline model evidence; corroborate before enforcement'})
        if probabilities is not None:
            result['top_class_probability'] = probabilities.max(axis=1)
        for field in ['window_id', 'timestamp_utc', 'switch_id', 'ingress_port']:
            if field in windows:
                result[field] = windows[field].to_numpy()
        return result

    def close(self):
        if self.spark is not None:
            self.spark.stop()
            self.spark = None
