"""Package executed artifacts and write a result-grounded three-person viva guide."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

from bda.verify import verify


def table(frame, columns):
    lines = ['| ' + ' | '.join(columns) + ' |', '| ' + ' | '.join(['---'] * len(columns)) + ' |']
    for _, row in frame.iterrows():
        lines.append('| ' + ' | '.join(f'{row[c]:.4f}' if isinstance(row[c], float) else str(row[c]) for c in columns) + ' |')
    return '\n'.join(lines)


def package(root, destination):
    run = root/'artifacts/bda/lab2-synthetic-seed42'
    reconciliation = verify(run)
    notebook_checks = json.loads((run/'notebook_validation.json').read_text())
    assert len(notebook_checks) == 4 and all(item['errors'] == 0 for item in notebook_checks)
    (run/'independent_validation.json').write_text(json.dumps(reconciliation, indent=2), encoding='utf-8')
    metrics = pd.read_csv(run/'model_metrics.csv')
    classes = pd.read_csv(run/'per_class_metrics.csv')
    selection = json.loads((run/'selection.json').read_text())
    operations = json.loads((run/'operating_points.json').read_text())
    selected = metrics[metrics.model == selection['winner']].iloc[0]
    benchmark = pd.read_csv(run/'engine_benchmark.csv').groupby('engine').seconds.median()
    quality = json.loads((run/'data_quality.json').read_text())
    contract = json.loads((run/'feature_contract.json').read_text())
    guide = f'''# Lab Evaluation 2 — presentation and viva guide

The evaluation trained nine distinct classifiers on all **39,000 synthetic windows**,
with **13 classes** and **{len(contract['features'])} retained numeric features**.
The shared split is **27,300 train / 5,850 validation / 5,850 test**.
The experiment used five Spark ML algorithms and four scikit-learn algorithms.

The model selected by validation macro F1 is **{selection['winner']}**.
Its test accuracy is **{selected.accuracy:.2%}**, macro F1 **{selected.f1_macro:.4f}**,
and conditional 95% stratified bootstrap interval **[{selected.f1_ci_low:.4f}, {selected.f1_ci_high:.4f}]**.
This interval describes sampling variation within this synthetic test population.
It does not cover domain shift, generator validity or independent capture sessions.

## Verified nine-model results

Rows are ordered by validation selection score, not by test score.

{table(metrics, ['model','engine','validation_macro_f1','accuracy','f1_macro','fit_seconds','amortized_prediction_ms'])}

Batch timings describe median completed 5,850-row prediction calls after a warmup.
They include Spark scheduling/collection and exclude already-completed preprocessing.
They are not single-request or end-to-end SDN latency measurements.

## What to say at the start

“We compare nine supervised algorithms on the same controlled synthetic SDN telemetry.
Spark performs data engineering and five model fits. Four complementary algorithms
run locally in scikit-learn after a bounded collection. We split before fitting
preprocessing, select on validation, and report final test and class-specific errors.
These are synthetic baseline results; improved measured data is the next experiment.”

## Three-person division

| Presenter | Three algorithms | Shared section |
|---|---|---|
| Satya | Logistic Regression, Decision Tree, Random Forest | dataset, feature exclusions, Spark workflow, fair selection |
| Prithvi | Gaussian Naive Bayes, MLP, RBF SVM | assumptions, scaling, nonlinear models, confidence versus margins |
| Roydon | KNN, Extra Trees, Histogram Gradient Boosting | serving cost, errors, output interpretation, alert policy |

Suggested presentation timing: 2 minutes shared introduction, 4 minutes per member,
2 minutes operational output, 2 minutes limitations and questions. Adjust to the rubric.
Every member must explain the shared split, target, metric definitions and synthetic scope.

## Data story and preprocessing

The unit is a generated **10-second aggregate window**, not a packet. Each class has
3,000 windows, so the attack prevalence is 12/13. This is artificially balanced across
traffic classes and is not a realistic general network prevalence.

The audit found no missing cells, exact duplicates or invalid rows requiring removal.
It found **{quality['table_size_above_capacity']:,}** table-size/capacity inconsistencies.
The generator clips occupancy while preserving larger raw table sizes. Its link-use
formula assumes 1 Gbit/s; old topology prose says 100 Mbit/s. Its ACK/SYN ratio is not
tracked handshake completion. Its `dropped_packet_rate` is a synthetic fraction.
These are documented as dataset limitations, not fixed by fabricating replacement values.

Remove IDs/time order, label/family, generation controls, scenario protocol/application,
random topology identities and the explicit CPU proxy. Drop constant window length.
Learn medians, means and sample standard deviations from training only. Preserve the
saved feature order and reuse those statistics at inference. No SMOTE is needed.
No high-rate outlier trimming is applied, because attack evidence may be extreme.

## Spark versus Python: precise explanation

Python is the language used to orchestrate both systems. Pandas is a local table library;
Spark is a distributed execution engine accessed through PySpark. Spark transformations
are lazy. An action such as collection or counting is needed to complete work.

For the same two-column Parquet read + per-class count/mean, median completed wall time
was **{benchmark['Pandas']:.4f} seconds with Pandas** and **{benchmark['Spark']:.4f} seconds with Spark**.
Both numerical results were reconciled. Spark startup is separately recorded.
Three trials alternate engine order; OS caches are not reset. Do not extrapolate to a
cluster or claim Spark must always be faster. This dataset fits in memory.

The nine different algorithms are not a controlled comparison of the same estimator
implemented in both libraries. Different objectives, hyperparameters and binned split
mechanisms affect their results. The notebook explicitly separates that question.

## Metric definitions to know

- Accuracy: correct windows / total windows.
- Precision: true positives / all predictions of that class; low precision creates false accusations.
- Recall: true positives / all actual windows of that class; low recall misses that pattern.
- F1: harmonic mean of precision and recall, penalizing an imbalance between them.
- Macro F1: mean class F1, giving all 13 classes equal importance.
- Weighted F1: support-weighted mean class F1. It equals macro F1 here because supports are equal.
- Macro recall equals accuracy here for the same balanced-support reason; this is not an API bug.
- ROC AUC: attack-score ranking across thresholds, comparing attack recall with benign false alarms.
- Average precision: attack precision/recall ranking summary; its baseline depends on prevalence.

Confusion matrices use true classes on rows and predictions on columns. Row normalization
means each row sums to one. A wrong attack subtype is different from predicting BENIGN
for an attack. Explain both the 13-class and binary views.

## Output use and the validation-selected operating point

For {selection['winner']}, the frozen attack threshold is **{operations[selection['winner']]['threshold']:.6g}**,
with score type **{operations[selection['winner']]['score_kind']}**.
At this threshold, test attack recall is **{operations[selection['winner']]['test_attack_recall']:.2%}**
and benign false-positive rate **{operations[selection['winner']]['test_benign_fpr']:.2%}**.
The threshold maximized validation attack recall under a validation benign-FPR cap of 1%.
Test error rates can differ and are not guarantees for a deployed network.

For probabilistic estimators, `1 - P(BENIGN)` is the attack score. SVM exposes a margin
score rather than a probability. A probability estimate is not automatically calibrated.
Keep score type, model version, feature schema, window identity and routing context.

Telemetry → aggregate window → schema check → saved preprocessing → classifier →
class/score record → corroborating per-flow evidence → policy action with expiry and rollback.
Use class labels for alert categorization, scores for prioritization and thresholds for
an operating decision. Do not block a whole switch port from an aggregate label alone.
The delivered examples are offline demonstrations and send no switch commands.

## Model-specific speaking notes
'''
    from build_bda_notebooks import ALGORITHMS
    for name, (member, engine, theory) in ALGORITHMS.items():
        row = metrics[metrics.model == name].iloc[0]
        weakest = classes[classes.model == name].nsmallest(3, 'recall')
        guide += f'\n### {name} — {member}\n\n{theory}\n\n'
        guide += f'Measured validation macro F1: **{row.validation_macro_f1:.4f}**; test macro F1: **{row.f1_macro:.4f}**; test accuracy: **{row.accuracy:.2%}**.\n\n'
        guide += 'Lowest-recall classes:\n\n' + table(weakest, ['class','precision','recall','f1-score','support']) + '\n\n'
        guide += 'Show this model’s saved confusion matrix. Explain one actual off-diagonal pair, the relevant feature overlap, and whether it changes the binary attack decision.\n'
    guide += '''
## Viva questions and defensible answers

1. **Why Spark for only 39,000 rows?** To demonstrate an auditable Spark pipeline and ML API;
   this size does not require a cluster. The measured aggregation comparison shows its overhead.
2. **Are all nine algorithms in Spark?** No: five use Spark ML; four use explicitly identified
   scikit-learn implementations. We do not call local KNN distributed training.
3. **Why not use Spark GBT for multiclass?** The native classifier’s supported label contract
   is binary; histogram boosting provides our multiclass boosting comparison.
4. **Why exclude time?** Generator classes occur in ordered time blocks; time would reveal labels.
5. **Why exclude protocol and application?** This generator fixes them by scenario, creating shortcuts.
   They may be useful in richer measured data with benign UDP/DNS and mixed services.
6. **Is every remaining feature measured?** No. These are synthetic measurement-style profiles.
7. **Why not use attack intensity as a feature?** It is a hidden generation control, not an inference-time observation.
8. **Why impute when no cells are missing?** A reusable training-fitted pipeline handles future nulls;
   current data needs no fabricated filling. Missing required columns still fail schema validation.
9. **Why scale trees?** Trees do not need scaling; shared transformed vectors make the input
   contract identical across algorithms. Scaling is important for KNN, SVM, LR and MLP.
10. **Why no random row resampling for better scores?** It would make selection biased.
11. **Why does NB struggle?** Its independent Gaussian-feature assumptions do not fit correlated,
   bounded and zero-inflated telemetry. Consult its actual class metrics before making a claim.
12. **Why can KNN fit quickly but serve slowly?** It stores training data and defers neighbor search to prediction.
13. **Why are SVM scores not percentages?** The margin is a decision/ranking score without probability calibration.
14. **What is the difference between RF and Extra Trees?** Extra Trees adds threshold randomization;
   the implemented training and backend differences are documented in each model section.
15. **What distinguishes boosting?** Trees are added sequentially to correct loss, rather than independently averaged.
16. **Why choose on validation instead of test?** Test-driven choice would expose the reported evaluation to selection bias.
17. **Is the test set entirely independent historically?** No. Previous work used this dataset;
   our new code and frozen split are reproducible, not a fresh external data collection.
18. **Does 100% synthetic binary recall prove a detector is ready?** No. Benign diversity is narrow,
   and real traffic changes feature distributions, prevalence and labeling quality.
19. **Can feature importance prove causality?** No; derived and correlated features complicate it further.
20. **What does the bootstrap interval cover?** Sampling variation of the fixed synthetic test population only.
21. **What changes when attack prevalence falls?** Alert precision can fall even at unchanged recall/FPR.
22. **Does ms/row prove line rate?** No. It is amortized batch inference on aggregate windows.
23. **How do you prevent stale notebook code?** Cloud setup cleans its marked disposable clone,
   checks out a named revision and records resolved commit plus source/dataset hashes.
24. **Where do results survive runtime resets?** Outside the source checkout: Drive for Colab;
   saved Kaggle version outputs; persistent local artifact folders for local runs.
25. **Can these models run on T4/A100/TPU automatically?** They can run on a CPU-equipped runtime,
   but these implementations do not use CUDA or TPU. We do not claim accelerator speedups.
26. **How will phase 2 change evaluation?** Collect independent measured sessions, verify definitions,
   include diverse benign services, then split by run/session/time and retrain with a new contract.

## Acceptance and remaining scope

Nine algorithms fitted and evaluated; shared splits and feature order saved; every held-out
prediction retained; metrics independently recomputed; selected estimator reload verified;
master and three team notebooks executed and exported; original synthetic data kept separate.
Inspect `notebook_validation.json` and `independent_validation.json` for the actual checks.

The new SDN capture notebook and live controller integration are outside this completed ML phase.
No claim is made that Google Colab grants Mininet’s required kernel/network capabilities.
That feasibility check belongs to the dataset-generation phase before any capture is promised.
'''
    destination.mkdir(parents=True, exist_ok=True)
    (destination/'PRESENTATION_AND_VIVA_GUIDE.md').write_text(guide, encoding='utf-8')
    shutil.copytree(run, destination/'results', dirs_exist_ok=True)
    source_dest = destination/'source'
    source_dest.mkdir(exist_ok=True)
    shutil.copytree(root/'analytics/bda', source_dest/'bda', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__'))
    for name in ['requirements-bda.txt','README.md','BDA_PLAN.md','build_bda_notebooks.py','execute_bda_notebooks.py','build_bda_delivery.py']:
        shutil.copy2(root/'analytics'/name, source_dest/name)
    for pattern in ['05_lab_evaluation_2_nine_models.*', '*_LA2.ipynb', '*_LA2.html']:
        for path in (root/'analytics').glob(pattern):
            shutil.copy2(path, destination/path.name)
    inputs = destination/'inputs'
    inputs.mkdir(exist_ok=True)
    shutil.copy2(root/'archive/legacy-2026-09-22/data/processed/sdn_ddos_versatile.parquet', inputs)
    manifest = {str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in destination.rglob('*') if p.is_file() and p.name != 'SHA256_MANIFEST.json'}
    (destination/'SHA256_MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Delivery:', destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package(Path(__file__).resolve().parents[1], args.output)
