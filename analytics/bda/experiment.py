"""Auditable shared-split Spark and scikit-learn model comparison.

The notebook calls these same functions; there is no second hidden implementation.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, average_precision_score, classification_report,
    confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split
from threadpoolctl import threadpool_limits

SEED = 42
EXCLUDED = {
    'scenario_id': 'scenario/window identity',
    'label': 'target', 'attack_family': 'target-derived family',
    'attack_intensity': 'generation parameter', 'attacker_count': 'generation parameter',
    'background_traffic_level': 'generation parameter',
    'controller_cpu_proxy_pct': 'explicit synthetic proxy, not measured CPU',
    'timestamp_utc': 'class-ordered generation time', 'window_id': 'encodes scenario index',
    'window_sequence': 'class-ordered sequence', 'hour_of_day': 'derived ordered time',
    'day_of_week': 'derived ordered time', 'experiment_id': 'experiment identifier',
    'src_host': 'c/a prefix directly exposes benign/attack', 'dst_host': 'host context',
    'site_id': 'random site identity', 'switch_id': 'random switch identity',
    'ingress_port': 'random port identity', 'egress_port': 'random port identity',
    'protocol': 'fixed per generated scenario', 'application': 'scenario-definition shortcut',
    'data_source': 'provenance', 'schema_version': 'provenance',
}


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding='utf-8')


def environment(root, dataset):
    def git(*args):
        try:
            return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            return 'unavailable'
    versions = {}
    for package in ['pyspark', 'numpy', 'pandas', 'scikit-learn', 'pyarrow', 'matplotlib']:
        versions[package] = importlib.metadata.version(package)
    return {
        'git_commit': git('rev-parse', 'HEAD'), 'git_dirty_files': git('status', '--porcelain'),
        'dataset_sha256': hashlib.sha256(Path(dataset).read_bytes()).hexdigest(),
        'dataset_path': str(dataset), 'python': sys.version, 'platform': platform.platform(),
        'cpu_count': os.cpu_count(), 'backend': 'CPU; Spark local mode plus scikit-learn',
        'accelerators': 'CUDA/TPU are not used by these estimators', 'packages': versions,
        'seed': SEED, 'split': [0.70, 0.15, 0.15],
        'source_sha256': {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted((Path(root) / 'analytics/bda').glob('*.py'))},
        'scope': 'Existing synthetic profiles; historical test exposure; no live-network validation',
    }


def start_spark():
    from pyspark.sql import SparkSession
    os.environ.setdefault('SPARK_LOCAL_IP', '127.0.0.1')
    os.environ['PYSPARK_PYTHON'] = sys.executable
    started = perf_counter()
    spark = (SparkSession.builder.master('local[4]').appName('SDN-DDoS-Lab-Evaluation-2')
             .config('spark.driver.memory', '2g')
             .config('spark.sql.shuffle.partitions', '4')
             .config('spark.default.parallelism', '4')
             .config('spark.ui.enabled', 'false')
             .config('spark.sql.execution.arrow.pyspark.enabled', 'true')
             .getOrCreate())
    spark.sparkContext.setLogLevel('ERROR')
    spark.range(1).count()  # force initialization; don't hide it in the first benchmark
    return spark, perf_counter() - started


def benchmark(spark, dataset, out):
    """Three completed read + class aggregation trials; OS cache is not reset."""
    from pyspark.sql import functions as F
    rows, answers = [], {}
    for repeat in range(3):
        for engine in (['Pandas', 'Spark'] if repeat % 2 == 0 else ['Spark', 'Pandas']):
            started = perf_counter()
            if engine == 'Pandas':
                source = pd.read_parquet(dataset, columns=['label', 'packet_rate'])
                answer = source.groupby('label').agg(windows=('label', 'size'), mean_pps=('packet_rate', 'mean')).sort_index()
            else:
                source = spark.read.parquet(str(dataset)).select('label', 'packet_rate')
                answer = (source.groupBy('label').agg(F.count('*').alias('windows'), F.avg('packet_rate').alias('mean_pps'))
                          .toPandas().set_index('label').sort_index())
            rows.append({'engine': engine, 'repeat': repeat + 1, 'seconds': perf_counter() - started})
            answers[engine] = answer
    np.testing.assert_array_equal(answers['Pandas'].windows, answers['Spark'].windows)
    np.testing.assert_allclose(answers['Pandas'].mean_pps, answers['Spark'].mean_pps, rtol=1e-10)
    result = pd.DataFrame(rows)
    result.to_csv(out / 'engine_benchmark.csv', index=False)
    return result


def load_and_audit(spark, dataset, out):
    from functools import reduce
    from pyspark.sql import functions as F
    source = spark.read.parquet(str(dataset))
    count_before = source.count()
    candidates = [field.name for field in source.schema if field.name not in EXCLUDED]
    nonnumeric = [name for name, kind in source.dtypes if name in candidates and kind not in ('double', 'float', 'long', 'int', 'bigint')]
    if nonnumeric:
        raise ValueError(f'Unclassified nonnumeric features: {nonnumeric}')
    clean = source.dropDuplicates()
    after_dedup = clean.count()
    conditions = [F.col('label').isNotNull(), F.col('window_id').isNotNull(),
                  F.col('window_seconds') > 0, F.col('packet_count') >= 0,
                  F.col('byte_count') >= 0, F.col('flow_count') >= 0]
    clean = clean.filter(reduce(lambda a, b: a & b, conditions))
    # Missing/infinite values become null; medians are fitted AFTER partitioning.
    for name in candidates:
        value = F.col(name).cast('double')
        clean = clean.withColumn(name, F.when(value.isNull() | F.isnan(value) | (F.abs(value) == float('inf')), None).otherwise(value))
    clean = clean.cache()
    count_clean = clean.count()
    frame = clean.toPandas().sort_values('window_id').reset_index(drop=True)
    if frame.window_id.duplicated().any():
        raise ValueError('Conflicting window identities: resolve before splitting')
    audit = []
    for name in frame:
        audit.append({'column': name, 'dtype': str(frame[name].dtype), 'missing': int(frame[name].isna().sum()),
                      'unique': int(frame[name].nunique()), 'use': 'excluded' if name in EXCLUDED else 'candidate numeric telemetry',
                      'reason': EXCLUDED.get(name, 'behavioral feature; synthetic measurement-style value')})
    audit = pd.DataFrame(audit)
    audit.to_csv(out / 'column_audit.csv', index=False)
    quality = {
        'source_rows': count_before, 'exact_duplicates_removed': count_before - after_dedup,
        'invalid_rows_removed': after_dedup - count_clean, 'clean_rows': count_clean,
        'columns': len(frame.columns), 'classes': sorted(frame.label.unique()),
        'missing_feature_cells': int(frame[candidates].isna().sum().sum()),
        'table_size_above_capacity': int((frame.flow_table_size > frame.flow_table_capacity).sum()),
        'occupancy_clipped': 'Generator clips size/capacity to [0,1]; does not fix raw counts',
        'link_units_issue': 'Generator divides byte_rate by 125,000,000 B/s (1 Gbit/s), README topology says 100 Mbit/s',
        'handshake_issue': 'ACK/SYN clipped at 2 is a synthetic ratio, not a tracked completed-handshake rate',
        'benign_coverage': 'Only TCP/HTTP benign scenario; no benign DNS/UDP/ICMP/flash crowds',
    }
    save_json(out / 'data_quality.json', quality)
    frame.to_parquet(out / 'clean_dataset.parquet', index=False)
    clean.unpersist()
    return frame, candidates, audit, quality


def partition(frame, candidates, out):
    indices = np.arange(len(frame))
    train, holdout = train_test_split(indices, test_size=.30, random_state=SEED, stratify=frame.label)
    valid, test = train_test_split(holdout, test_size=.50, random_state=SEED, stratify=frame.label.iloc[holdout])
    assert not (set(train) & set(valid) or set(train) & set(test) or set(valid) & set(test))
    assert len(train) + len(valid) + len(test) == len(frame)
    # All-null and constant columns are determined only from training data.
    features = [name for name in candidates if frame.iloc[train][name].nunique() > 1]
    assert not set(features) & set(EXCLUDED)
    fingerprints = pd.util.hash_pandas_object(frame[features], index=False)
    for left, right in [(train, valid), (train, test), (valid, test)]:
        if set(fingerprints.iloc[left]) & set(fingerprints.iloc[right]):
            raise ValueError('Repeated feature vectors cross split boundaries; use grouped splitting for this dataset')
    labels = sorted(frame.label.unique())
    parts = {}
    manifest = []
    for name, positions in [('train', train), ('validation', valid), ('test', test)]:
        part = frame.iloc[positions].copy().sort_values('window_id').reset_index(drop=True)
        part['target'] = part.label.map({label: i for i, label in enumerate(labels)}).astype(int)
        parts[name] = part
        manifest.append(part[['window_id', 'label']].assign(split=name))
        assert set(part.label) == set(labels)
    pd.concat(manifest).to_csv(out / 'split_manifest.csv', index=False)
    save_json(out / 'feature_contract.json', {'features': features, 'labels': labels, 'excluded': EXCLUDED,
                                             'train_constant_columns': sorted(set(candidates) - set(features))})
    return parts, features, labels


def preprocess(spark, parts, features, out):
    from pyspark.ml import Pipeline
    from pyspark.ml.feature import Imputer, StandardScaler, VectorAssembler
    from pyspark.ml.functions import vector_to_array
    from pyspark.sql import functions as F
    imputed = [f'imp_{i}' for i in range(len(features))]
    pipeline = Pipeline(stages=[
        Imputer(inputCols=features, outputCols=imputed, strategy='median', relativeError=0.001),
        VectorAssembler(inputCols=imputed, outputCol='raw_features'),
        StandardScaler(inputCol='raw_features', outputCol='features', withMean=True, withStd=True),
    ])
    raw = {name: spark.createDataFrame(part[['window_id', 'target', *features]].rename(columns={'target': 'label'}))
           for name, part in parts.items()}
    fitted = pipeline.fit(raw['train'])
    fitted.write().overwrite().save(str(out / 'preprocessor.spark'))
    vectors, arrays = {}, {}
    for name in parts:
        transformed = fitted.transform(raw[name]).select('window_id', 'label', 'features').cache()
        transformed.count()
        vectors[name] = transformed
        collected = transformed.select('window_id', vector_to_array('features').alias('values')).toPandas().set_index('window_id')
        arrays[name] = np.vstack(collected.loc[parts[name].window_id, 'values'].to_numpy())
        assert np.isfinite(arrays[name]).all()
    # A portable equivalent uses Spark's exact fitted statistics for Python serving.
    medians = fitted.stages[0].surrogateDF.first().asDict()
    portable = {'features': features, 'median': [float(medians[c]) for c in features],
                'mean': fitted.stages[2].mean.toArray().tolist(),
                'std': fitted.stages[2].std.toArray().tolist()}
    save_json(out / 'preprocessing.json', portable)
    # The direct portable transform must match Spark's transform numerically.
    np.testing.assert_allclose(transform_numeric(parts['test'], portable), arrays['test'], atol=1e-9)
    return fitted, vectors, arrays, portable


def transform_numeric(frame, stats):
    values = frame[stats['features']].to_numpy(dtype=float)
    values[~np.isfinite(values)] = np.nan
    values = np.where(np.isnan(values), np.asarray(stats['median']), values)
    standard_deviation = np.asarray(stats['std'])
    return np.divide(values - np.asarray(stats['mean']), standard_deviation,
                     out=np.zeros_like(values), where=standard_deviation != 0)


def specifications(dimension, classes):
    from pyspark.ml.classification import (
        DecisionTreeClassifier, LogisticRegression, MultilayerPerceptronClassifier,
        NaiveBayes, RandomForestClassifier,
    )
    from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.svm import SVC
    return [
        ('Logistic Regression', 'Spark', [
            LogisticRegression(family='multinomial', maxIter=100, regParam=r, tol=1e-5) for r in [.001, .01]]),
        ('Decision Tree', 'Spark', [
            DecisionTreeClassifier(maxDepth=d, minInstancesPerNode=5, maxBins=32, seed=SEED) for d in [8, 12]]),
        ('Random Forest', 'Spark', [
            RandomForestClassifier(numTrees=40, maxDepth=d, minInstancesPerNode=5, maxBins=32,
                                   featureSubsetStrategy='sqrt', seed=SEED) for d in [8, 12]]),
        ('Gaussian Naive Bayes', 'Spark', [NaiveBayes(modelType='gaussian')]),
        ('Multilayer Perceptron', 'Spark', [
            MultilayerPerceptronClassifier(layers=[dimension, h, classes], maxIter=100,
                                          blockSize=128, seed=SEED, tol=1e-5) for h in [32, 64]]),
        ('K Nearest Neighbors', 'scikit-learn', [
            KNeighborsClassifier(n_neighbors=k, weights='distance', n_jobs=4) for k in [7, 15]]),
        ('RBF Support Vector Machine', 'scikit-learn', [
            SVC(C=c, kernel='rbf', gamma='scale', probability=False, cache_size=512,
                decision_function_shape='ovr', random_state=SEED) for c in [1., 10.]]),
        ('Extra Trees', 'scikit-learn', [
            ExtraTreesClassifier(n_estimators=100, max_depth=d, min_samples_leaf=2,
                                 n_jobs=4, random_state=SEED) for d in [16, None]]),
        ('Histogram Gradient Boosting', 'scikit-learn', [
            HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=leaves,
                                           learning_rate=.1, l2_regularization=1.,
                                           early_stopping=True, random_state=SEED) for leaves in [15, 31]]),
    ]


def model_parameters(estimator, engine):
    if engine == 'Spark':
        return {key.name: value for key, value in estimator.extractParamMap().items()}
    return estimator.get_params()


def predict(model, engine, split, vectors, arrays, parts):
    if engine == 'Spark':
        table = model.transform(vectors[split]).select('window_id', 'prediction', 'probability').toPandas().set_index('window_id')
        table = table.loc[parts[split].window_id]
        prediction = table.prediction.to_numpy(dtype=int)
        probabilities = np.vstack([value.toArray() for value in table.probability])
        return prediction, probabilities, None
    values = arrays[split]
    prediction = model.predict(values)
    if hasattr(model, 'predict_proba'):
        return prediction, model.predict_proba(values), None
    return prediction, None, model.decision_function(values)


def train_models(vectors, arrays, parts, features, labels, out):
    fitted, selection_rows = {}, []
    for name, engine, candidates in specifications(len(features), len(labels)):
        print(f'Training {name} ({engine})', flush=True)
        best = None
        for index, estimator in enumerate(candidates):
            started = perf_counter()
            with threadpool_limits(limits=4):
                model = (estimator.fit(vectors['train']) if engine == 'Spark'
                         else estimator.fit(arrays['train'], parts['train'].target))
            fit_seconds = perf_counter() - started
            prediction, _, _ = predict(model, engine, 'validation', vectors, arrays, parts)
            score = f1_score(parts['validation'].target, prediction, average='macro', zero_division=0)
            params = model_parameters(estimator, engine)
            selection_rows.append({'model': name, 'engine': engine, 'candidate': index,
                                   'validation_macro_f1': score, 'fit_seconds': fit_seconds,
                                   'parameters': json.dumps(params, default=str)})
            print(f'  candidate {index}: validation macro F1={score:.5f}; fit={fit_seconds:.1f}s', flush=True)
            if best is None or score > best['validation_macro_f1']:
                best = {'model': model, 'engine': engine, 'validation_macro_f1': score,
                        'fit_seconds': fit_seconds, 'candidate': index, 'parameters': params}
        fitted[name] = best
        slug = name.lower().replace(' ', '_')
        if engine == 'Spark':
            best['model'].write().overwrite().save(str(out / 'models' / (slug + '.spark')))
        else:
            joblib.dump(best['model'], out / 'models' / (slug + '.joblib'))
        pd.DataFrame(selection_rows).to_csv(out / 'tuning_results.csv', index=False)
    winner = max(fitted, key=lambda name: fitted[name]['validation_macro_f1'])
    # Selection is persisted BEFORE any test prediction is requested.
    save_json(out / 'selection.json', {'winner': winner, 'rule': 'maximum validation macro F1; first candidate wins ties',
                                     'models': {name: {k: v for k, v in record.items() if k != 'model'}
                                                for name, record in fitted.items()}})
    return fitted, winner


def attack_score(probability, margin, benign_index):
    if probability is not None:
        return 1 - probability[:, benign_index]
    # Negative benign OVR margin: ranking score only, NOT a probability.
    return -margin[:, benign_index]


def threshold_from_validation(truth, score, max_false_alarm=.01):
    from sklearn.metrics import roc_curve
    false_positive, true_positive, thresholds = roc_curve(truth, score, drop_intermediate=False)
    eligible = np.flatnonzero((false_positive <= max_false_alarm) & np.isfinite(thresholds))
    if not len(eligible):
        return float(np.nextafter(np.max(score), np.inf))
    # Highest recall; among ties, fewer false alarms, then stricter threshold.
    best = sorted(eligible, key=lambda i: (-true_positive[i], false_positive[i], -thresholds[i]))[0]
    return float(thresholds[best])


def summarize(truth, predicted, scores, benign_index):
    attack_truth = np.asarray(truth) != benign_index
    attack_predicted = predicted != benign_index
    tn, fp, fn, tp = confusion_matrix(attack_truth, attack_predicted, labels=[False, True]).ravel()
    return {
        'accuracy': accuracy_score(truth, predicted),
        'precision_macro': precision_score(truth, predicted, average='macro', zero_division=0),
        'recall_macro': recall_score(truth, predicted, average='macro', zero_division=0),
        'f1_macro': f1_score(truth, predicted, average='macro', zero_division=0),
        'f1_weighted': f1_score(truth, predicted, average='weighted', zero_division=0),
        'attack_recall_argmax': tp / (tp + fn), 'benign_fpr_argmax': fp / (fp + tn),
        'attack_roc_auc': roc_auc_score(attack_truth, scores),
        'attack_average_precision': average_precision_score(attack_truth, scores),
        'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp),
    }


def evaluate(fitted, winner, vectors, arrays, parts, labels, out):
    benign_index = labels.index('BENIGN')
    truth = parts['test'].target.to_numpy()
    result_rows, class_rows, predictions, operations = [], [], {}, {}
    for name, record in fitted.items():
        model, engine = record['model'], record['engine']
        vp, vprob, vmargin = predict(model, engine, 'validation', vectors, arrays, parts)
        validation_scores = attack_score(vprob, vmargin, benign_index)
        threshold = threshold_from_validation(parts['validation'].target.to_numpy() != benign_index, validation_scores)
        # One warmup followed by three completed prediction trials, same 5850 rows.
        predict(model, engine, 'test', vectors, arrays, parts)
        timings = []
        for _ in range(3):
            started = perf_counter()
            prediction, probability, margin = predict(model, engine, 'test', vectors, arrays, parts)
            timings.append(perf_counter() - started)
        score = attack_score(probability, margin, benign_index)
        values = summarize(truth, prediction, score, benign_index)
        values.update({'model': name, 'engine': engine, 'validation_macro_f1': record['validation_macro_f1'],
                       'selected_by_validation': name == winner, 'fit_seconds': record['fit_seconds'],
                       'prediction_batch_seconds': float(np.median(timings)),
                       'amortized_prediction_ms': 1000 * float(np.median(timings)) / len(truth)})
        # Stratified bootstrap: sampling uncertainty on THIS synthetic test population only.
        rng = np.random.default_rng(SEED)
        groups = [np.flatnonzero(truth == i) for i in range(len(labels))]
        bootstrap = []
        for _ in range(200):
            sample = np.concatenate([rng.choice(group, len(group), replace=True) for group in groups])
            bootstrap.append(f1_score(truth[sample], prediction[sample], average='macro', zero_division=0))
        values['f1_ci_low'], values['f1_ci_high'] = np.quantile(bootstrap, [.025, .975])
        result_rows.append(values)
        report = classification_report(truth, prediction, labels=list(range(len(labels))), target_names=labels,
                                       output_dict=True, zero_division=0)
        for label in labels:
            class_rows.append({'model': name, 'class': label, **report[label]})
        ops_pred = score >= threshold
        tn, fp, fn, tp = confusion_matrix(truth != benign_index, ops_pred, labels=[False, True]).ravel()
        operations[name] = {'threshold': threshold, 'score_kind': 'uncalibrated probability estimate' if probability is not None else 'negative benign SVM margin',
                            'validation_fpr_limit': .01, 'test_attack_recall': float(tp / (tp + fn)),
                            'test_benign_fpr': float(fp / (tn + fp)), 'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)}
        saved = pd.DataFrame({'window_id': parts['test'].window_id, 'actual': np.asarray(labels)[truth],
                              'predicted': np.asarray(labels)[prediction], 'attack_score': score,
                              'threshold_attack': ops_pred})
        if probability is not None:
            saved['top_class_probability'] = probability.max(axis=1)
        slug = name.lower().replace(' ', '_')
        saved.to_parquet(out / 'predictions' / (slug + '.parquet'), index=False)
        predictions[name] = {'pred': prediction, 'proba': probability, 'score': score, 'table': saved}
        print(f'Test {name}: macro F1={values["f1_macro"]:.5f}', flush=True)
    metrics = pd.DataFrame(result_rows).sort_values('validation_macro_f1', ascending=False)
    classes = pd.DataFrame(class_rows)
    metrics.to_csv(out / 'model_metrics.csv', index=False)
    classes.to_csv(out / 'per_class_metrics.csv', index=False)
    save_json(out / 'operating_points.json', operations)
    # Cost is an explicit hypothetical planning scenario, not measured money.
    cost_rows = []
    for name, row in operations.items():
        for prevalence in [.001, .01, .1]:
            tp = prevalence * row['test_attack_recall']
            fp = (1 - prevalence) * row['test_benign_fpr']
            cost_rows.append({'model': name, 'assumed_attack_prevalence': prevalence,
                              'expected_alert_precision': tp / (tp + fp) if tp + fp else 0.,
                              'expected_false_alarms_per_10000': 10000 * fp,
                              'expected_missed_attacks_per_10000': 10000 * prevalence * (1 - row['test_attack_recall'])})
    pd.DataFrame(cost_rows).to_csv(out / 'prevalence_scenarios.csv', index=False)
    return metrics, classes, predictions, operations


def reload_check(fitted, winner, vectors, arrays, parts, out):
    record = fitted[winner]
    slug = winner.lower().replace(' ', '_')
    if record['engine'] == 'Spark':
        reloaded = record['model'].__class__.load(str(out / 'models' / (slug + '.spark')))
    else:
        reloaded = joblib.load(out / 'models' / (slug + '.joblib'))
    before, _, _ = predict(record['model'], record['engine'], 'test', vectors, arrays, parts)
    after, _, _ = predict(reloaded, record['engine'], 'test', vectors, arrays, parts)
    np.testing.assert_array_equal(before, after)
    return {'winner_reload_identical_predictions': True, 'test_rows_compared': len(before)}


def inference_examples(winner, predictions, operations, parts, out):
    table = predictions[winner]['table'].copy()
    context = parts['test'].set_index('window_id')[['switch_id', 'ingress_port']]
    examples = []
    # One true example per class, including wrong predictions when present.
    for _, group in table.groupby('actual', sort=True):
        wrong = group[group.actual != group.predicted]
        examples.append((wrong if len(wrong) else group).iloc[0])
    sample = pd.DataFrame(examples).set_index('window_id').join(context).reset_index()
    sample['proposed_action'] = np.where(sample.threshold_attack, 'ALERT_AND_REQUEST_CORROBORATION', 'OBSERVE')
    sample['model'] = winner
    sample['scope'] = 'offline demonstration; no switch command sent'
    sample.to_csv(out / 'inference_examples.csv', index=False)
    return sample


def setup_run(root, output, dataset=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for subdirectory in ['models', 'predictions', 'figures']:
        (output / subdirectory).mkdir(exist_ok=True)
    dataset = Path(dataset) if dataset else Path(root) / 'archive/legacy-2026-09-22/data/processed/sdn_ddos_versatile.parquet'
    save_json(output / 'environment.json', environment(root, dataset))
    return dataset, output


def main():
    import argparse
    from . import visuals
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dataset', type=Path)
    args = parser.parse_args()
    dataset, out = setup_run(args.root, args.output, args.dataset)
    spark, startup = start_spark()
    save_json(out / 'spark_runtime.json', {'startup_seconds': startup, 'version': spark.version,
                                         'master': spark.sparkContext.master})
    try:
        timings = benchmark(spark, dataset, out)
        frame, candidates, audit, quality = load_and_audit(spark, dataset, out)
        parts, features, labels = partition(frame, candidates, out)
        processor, vectors, arrays, stats = preprocess(spark, parts, features, out)
        visuals.dataset_figures(frame, features, parts, timings, out)
        fitted, winner = train_models(vectors, arrays, parts, features, labels, out)
        metrics, classes, predictions, operations = evaluate(fitted, winner, vectors, arrays, parts, labels, out)
        examples = inference_examples(winner, predictions, operations, parts, out)
        visuals.result_figures(metrics, classes, predictions, fitted, labels, parts, features, arrays, winner, out)
        checks = reload_check(fitted, winner, vectors, arrays, parts, out)
        checks.update({'nine_algorithms': len(metrics) == 9, 'all_test_rows_used': all(len(p['pred']) == len(parts['test']) for p in predictions.values()),
                       'feature_count': len(features), 'winner': winner, 'status': 'complete'})
        save_json(out / 'validation.json', checks)
        print(metrics[['model', 'engine', 'validation_macro_f1', 'f1_macro', 'accuracy']].to_string(index=False))
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
