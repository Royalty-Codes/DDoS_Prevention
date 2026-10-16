"""Build master and three team notebooks using one reusable experiment backend."""
from pathlib import Path
import textwrap

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'analytics'

ALGORITHMS = {
    'Logistic Regression': (
        'Satya', 'Spark',
        r'''A linear multiclass classifier. Each class receives a score $z_k=w_k^T x+b_k$;
softmax converts scores to $P(y=k\mid x)=e^{z_k}/\sum_j e^{z_j}$. Training minimizes
regularized cross-entropy. Despite its name, this is classification, not numeric regression.

**Execution:** standardized feature vector → 13 linear scores → softmax → highest-score class.
Compare `regParam=0.001` and `0.01`; maximum 100 optimization iterations. Larger regularization
penalizes large weights. Scaling prevents units from dominating the penalty.

**Strength:** fast, useful linear baseline. **Failure mode:** nonlinear class overlap cannot be
resolved by a single linear boundary; correlated derived counters make coefficient interpretation unstable.
Its probability estimates can be miscalibrated. Use its class output for a traffic label and
`1 - P(BENIGN)` for an attack score; validate a threshold before operational use.'''),
    'Decision Tree': (
        'Satya', 'Spark',
        r'''A tree recursively partitions data with questions such as `tcp_syn_ratio <= threshold`.
For class proportions $p_k$, Gini impurity is $1-\sum_k p_k^2$. A split reduces weighted child impurity.
Prediction follows one root-to-leaf path; the leaf class distribution supplies probabilities.

**Execution:** one feature test per node → choose left/right → leaf counts → class vote.
Compare depths 8 and 12, minimum 5 training windows per node, 32 feature bins.
Spark uses binned split candidates, so this need not match a scikit-learn tree exactly.

**Strength:** understandable decision paths, nonlinear interactions, cheap serving.
**Failure mode:** unstable under small data changes, deep trees memorize generator patterns.
Use paths to explain alerts, but a path is a learned correlation rather than a causal attack signature.'''),
    'Random Forest': (
        'Satya', 'Spark',
        r'''A forest fits randomized decision trees and averages their class distributions.
Random feature subsets reduce correlation among trees; averaging reduces variance relative to a single tree.

**Execution:** send one window to every tree → average leaf probabilities → class with largest average.
Use 40 trees, `sqrt` feature subsets, minimum 5 instances/node, depths 8 and 12.
Trees can be trained across Spark partitions. In local mode these workers share one laptop.

**Strength:** nonlinear tabular baseline with interpretable feature rankings.
**Failure mode:** larger model and inference cost; impurity importance favors certain split-rich
features and spreads relevance across correlated counters. It does not prove causality.
Use predictions for an alert queue and rankings for investigating which telemetry deserves attention.'''),
    'Gaussian Naive Bayes': (
        'Prithvi', 'Spark',
        r'''Bayes' rule gives $P(y\mid x)\propto P(y)P(x\mid y)$. The naive assumption factorizes
the likelihood into independent features: $P(x\mid y)=\prod_j P(x_j\mid y)$.
Gaussian NB estimates a separate feature mean and variance within each class.
Computation uses log probabilities to avoid multiplying tiny numbers.

**Execution:** class prior + sum of Gaussian log likelihoods → normalized class probabilities → argmax.
This is one fixed analytical baseline; no fake hyperparameter search is performed.
Gaussian NB accepts continuous standardized features; multinomial NB's nonnegative-count assumptions
would be inappropriate for negative standardized telemetry.

**Strength:** inexpensive training and serving. **Failure mode:** packet count and packet rate
are dependent, violating its factorization assumption. Distributions are also skewed, bounded and
zero-inflated. Probability confidence may be extreme and wrong. Use it as a diagnostic baseline,
and explain weak results through its assumptions rather than hiding them.'''),
    'Multilayer Perceptron': (
        'Prithvi', 'Spark',
        r'''A neural classifier repeatedly computes weighted sums and nonlinear activations.
For a hidden layer, $h=\sigma(W_1x+b_1)$; the output layer uses softmax class probabilities.
Backpropagation computes derivatives; Spark's solver updates the parameters.

**Execution:** standardized telemetry → hidden layer of 32 or 64 units → 13 output units.
Maximum 100 optimization iterations, block size 128, seed 42. The feature dimension comes
from the fitted contract rather than a hardcoded input width. CPU Spark training does not use CUDA or TPU.

**Strength:** flexible nonlinear interactions. **Failure mode:** optimization may stop before
convergence; increased flexibility needs careful validation. The experiment is a bounded CPU comparison,
not proof of an optimally tuned neural detector. Use its probability vector for ranked alternatives
and review near-tied predictions; neural confidence is not a guarantee.'''),
    'K Nearest Neighbors': (
        'Roydon', 'scikit-learn',
        r'''KNN stores training examples. For a new window, calculate distances to training windows,
retrieve the $k$ closest, and combine their labels. Euclidean distance is
$d(x,z)=\sqrt{\sum_j(x_j-z_j)^2}$. Distance weighting gives nearby neighbors more influence.

**Execution:** standardized query → nearest stored vectors → weighted vote → class probabilities.
Compare 7 and 15 neighbors. The exact same Spark-fitted numeric vectors are collected to the driver.
This collection is safe at the current size but is not distributed KNN.

**Strength:** simple reference case reasoning; almost no fitting work.
**Failure mode:** prediction and storage grow with training data; irrelevant or redundant dimensions
distort distance. Tiny fit time does not imply inexpensive deployment. Use nearest examples to
illustrate similarity, while checking whether those examples represent the real environment.'''),
    'RBF Support Vector Machine': (
        'Prithvi', 'scikit-learn',
        r'''An SVM seeks class-separating margins. The RBF kernel
$K(x,z)=\exp(-\gamma\lVert x-z\rVert^2)$ measures nonlinear similarity without explicitly constructing
the transformed feature space. Larger $C$ penalizes training errors more strongly.

**Execution:** scaled vector → similarities to support vectors → pairwise class decisions → class vote.
Compare `C=1` and `10`, `gamma='scale'`. `SVC` trains multiclass one-vs-one internally;
`decision_function_shape='ovr'` exposes class-shaped decision scores.

**Strength:** strong nonlinear tabular baseline. **Failure mode:** kernel training and serving can
be expensive as support-vector count grows. `probability=False` intentionally avoids expensive
internal calibration. Its decision margins are **not probabilities**; the attack ranking score is
the negative benign-class margin. Never write '90% attack probability' from this score.'''),
    'Extra Trees': (
        'Roydon', 'scikit-learn',
        r'''Extremely Randomized Trees add split-threshold randomization to a tree ensemble.
Instead of optimizing every threshold as in a conventional forest, random candidate thresholds
increase diversity; the ensemble averages tree class estimates.

**Execution:** window → 100 randomized trees → averaged class probabilities → predicted label.
Compare depth 16 and unrestricted depth, with minimum 2 rows per leaf and seed 42.
This is a multicore Python model after bounded Spark-to-driver collection, not Spark ML training.

**Strength:** often effective on numeric tabular data with little feature engineering.
**Failure mode:** deep trees can memorize narrow synthetic distributions; model storage and serving
cost rise with tree count. Treat importance as association, and revalidate on independent captures
before using these probabilities for controller decisions.'''),
    'Histogram Gradient Boosting': (
        'Roydon', 'scikit-learn',
        r'''Boosting adds trees sequentially to reduce the current loss. For multiclass classification,
the additive class scores are converted to probabilities with softmax. A learning rate shrinks
each update; histogram bins reduce the cost of considering continuous split thresholds.

**Execution:** initial class scores → add corrections from successive trees → probabilities → argmax.
Use maximum 100 iterations, learning rate 0.1, L2 penalty 1, and compare 15 versus 31 leaf nodes.
Early stopping uses an internal subset drawn only from the external training split; the external
validation set still chooses between candidates. This is different from Spark's binary-only GBTClassifier.

**Strength:** powerful nonlinear numeric-table baseline. **Failure mode:** sequential training,
more tuning choices, and overfitting to generator-specific relationships. Use its class distribution
to produce a diagnostic alert with alternatives and explain errors on similar amplification classes.'''),
}

BOOTSTRAP = r'''
from pathlib import Path
import os, subprocess, sys, shutil

IN_COLAB = 'google.colab' in sys.modules or bool(os.environ.get('COLAB_RELEASE_TAG'))
IN_KAGGLE = bool(os.environ.get('KAGGLE_KERNEL_RUN_TYPE'))
REPO_URL = 'https://github.com/Royalty-Codes/DDoS_Prevention.git'
REVISION = os.environ.get('BDA_REVISION', 'bda-nine-models')

if IN_COLAB or IN_KAGGLE:
    # This exact disposable path is separate from persistent experiment results.
    BASE = Path('/content' if IN_COLAB else '/kaggle/working')
    ROOT = BASE / 'ddos-bda-checkout'
    marker = ROOT / '.codex-bda-disposable'
    if ROOT.exists():
        if not marker.is_file() or ROOT.resolve() != (BASE / 'ddos-bda-checkout').resolve():
            raise RuntimeError('Refusing to delete an unmarked checkout; choose an empty disposable path.')
        shutil.rmtree(ROOT)
    subprocess.run(['git', 'clone', REPO_URL, str(ROOT)], check=True)
    marker.touch()
    subprocess.run(['git', '-C', str(ROOT), 'fetch', '--all', '--tags', '--prune'], check=True)
    subprocess.run(['git', '-C', str(ROOT), 'checkout', '--detach', REVISION], check=True)
    if shutil.which('java') is None:
        subprocess.run(['apt-get', 'update', '-qq'], check=True)
        subprocess.run(['apt-get', 'install', '-y', '-qq', 'openjdk-17-jre-headless'], check=True)
    java17 = Path('/usr/lib/jvm/java-17-openjdk-amd64')
    if java17.is_dir():
        os.environ['JAVA_HOME'] = str(java17)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-r', str(ROOT/'analytics/requirements-bda.txt')], check=True)
    if IN_COLAB:
        from google.colab import drive
        drive.mount('/content/drive')
        RESULTS_BASE = Path('/content/drive/MyDrive/SDN_DDoS_BDA')
    else:
        RESULTS_BASE = Path('/kaggle/working/SDN_DDoS_BDA')
        print('Kaggle: save a notebook version with outputs to retain results after this session.')
else:
    current = Path.cwd().resolve()
    roots = [current, *current.parents]
    ROOT = next((p for p in roots if (p/'analytics/bda/experiment.py').is_file()), None)
    if ROOT is None:
        configured = os.environ.get('BDA_ROOT')
        if not configured:
            raise RuntimeError('Run from the repository or set BDA_ROOT to its absolute path.')
        ROOT = Path(configured).resolve()
    RESULTS_BASE = Path(os.environ.get('BDA_RESULTS_BASE', str(ROOT/'artifacts/bda')))

sys.path.insert(0, str(ROOT/'analytics'))
RUN_ID = os.environ.get('BDA_RUN_ID', 'lab2-synthetic-seed42')
RUN_DIR = RESULTS_BASE / RUN_ID
# To retrain an existing run, set BDA_RETRAIN=1 and choose a NEW BDA_RUN_ID.
RETRAIN = os.environ.get('BDA_RETRAIN', '0') == '1' or not (RUN_DIR/'validation.json').is_file()
print('Environment:', 'Colab CPU' if IN_COLAB else 'Kaggle CPU' if IN_KAGGLE else 'Local CPU')
print('Source:', ROOT, '\nResults:', RUN_DIR, '\nRetrain:', RETRAIN)
'''


def build(person=None):
    cells = []
    def md(text):
        cells.append(nbf.v4.new_markdown_cell(textwrap.dedent(text).strip()))
    def code(text):
        cells.append(nbf.v4.new_code_cell(textwrap.dedent(text).strip()))
    title = 'Lab Evaluation 2 — SDN DDoS: Spark + Nine ML Algorithms' if person is None else f'{person} — Lab Evaluation 2: Three Algorithms and Their Inferences'
    md(f'''# {title}

**Dataset:** original controlled synthetic SDN profiles, 39,000 windows, 63 columns, 13 classes.
**Team:** Satya, Prithvi, Roydon. **Backend:** five Spark ML algorithms and four scikit-learn algorithms.

This notebook explains what the data means, how each model works, how results were obtained,
and what a model output could do in an SDN alerting system. It does not claim real-network
detection effectiveness, production deployment, or a completed mitigation loop.

The Satya / Prithvi / Roydon LA1 notebooks guide the data-overview, traffic-behavior and SDN-telemetry
organization. Their archived 110,000-row measured dataset is **not merged** with this synthetic experiment.
The newer 28-column capture pipeline remains separate and can support a later retraining phase.''')
    md('''## 1. Aim, scope and success criteria

1. Audit the complete existing dataset, including missing values, class balance, units and leakage.
2. Compare nine distinct classifiers using identical saved splits and training-only preprocessing.
3. Select hyperparameters and an overall model on validation macro F1 before reading test metrics.
4. Explain class errors, benign false alarms, missed attacks, confidence, and compute costs.
5. Persist the fitted preprocessing, model, label mapping, predictions and reproducibility metadata.

**Important limitation:** previous experiments already used this dataset. This is not a pristine external
test population. Random splits estimate performance on the same generator distribution, not independent
network sessions. A later capture needs session/run-grouped or chronological evaluation.''')
    md('''## 2. Deterministic setup and persistent results

The next cell is the first executable setup cell. Local execution uses the current checkout without
resetting it. Colab/Kaggle clean and re-clone only a marked disposable checkout, then resolve the
requested branch/commit. Results live outside that checkout. Push the branch before cloud execution.

Use Python 3.12, Java 17, and the pinned dependency file. If Java is absent in Colab, install
`openjdk-17-jre-headless` and set `JAVA_HOME` to `/usr/lib/jvm/java-17-openjdk-amd64` before starting Spark.
CPU is appropriate. Detecting a GPU/TPU does not make these estimators use it.

The full run is trained when its artifact directory is absent. Reopening a completed run reads its
recorded outputs, verifies the source dataset hash, and labels that mode explicitly. For a fresh run,
set `BDA_RETRAIN=1` and a new `BDA_RUN_ID`; do not overwrite a previous experiment.''')
    code(BOOTSTRAP)
    code('''import json, hashlib, platform
import numpy as np
import pandas as pd
from IPython.display import display, Image, Markdown
from bda import experiment as exp

DATASET = Path(os.environ.get('BDA_DATASET', str(ROOT/'archive/legacy-2026-09-22/data/processed/sdn_ddos_versatile.parquet')))
if not DATASET.is_file() and IN_COLAB:
    DATASET = RESULTS_BASE/'inputs/sdn_ddos_versatile.parquet'
    if not DATASET.is_file():
        from google.colab import files
        print('Upload the original sdn_ddos_versatile.parquet from the delivery bundle.')
        uploaded = files.upload()
        if 'sdn_ddos_versatile.parquet' not in uploaded:
            raise ValueError('Expected the original Parquet filename; no substitute is accepted.')
        DATASET.parent.mkdir(parents=True, exist_ok=True)
        DATASET.write_bytes(uploaded['sdn_ddos_versatile.parquet'])
if not DATASET.is_file():
    raise FileNotFoundError('Synthetic data is not versioned in Git. Upload/download the original Parquet, then set BDA_DATASET to its path. Never silently substitute another dataset.')
def show_figure(name):
    display(Image(filename=str(RUN_DIR/'figures'/f'{name}.png')))
pd.set_option('display.max_columns', 30)
pd.set_option('display.max_rows', 100)
print('Dataset:', DATASET)
print('Java:', subprocess.run(['java', '-version'], capture_output=True, text=True).stderr.splitlines()[0])
print('Resolved source commit:', subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'], text=True).strip())''')
    md('''## 3. Reproducible execution of the experiment

The reusable source is `analytics/bda/experiment.py`; plots are in `analytics/bda/visuals.py`.
The following command executes the complete pipeline, including all candidate fits, validation selection,
test evaluation, model persistence and reload checks. The notebook is a runnable companion to those modules.
It never substitutes saved scores for an unexecuted experiment.

```bash
python -m bda.experiment --root PROJECT_ROOT --dataset ORIGINAL_PARQUET --output PERSISTENT_RUN_DIR
```

Run that command with `analytics` on `PYTHONPATH`. In artifact-reading mode, the cell checks
the recorded dataset hash and completion marker before showing any conclusions.''')
    code('''if RETRAIN:
    if (RUN_DIR/'validation.json').exists():
        raise RuntimeError('Choose a new BDA_RUN_ID for retraining to preserve the previous run.')
    run_env = os.environ.copy()
    run_env['PYTHONPATH'] = str(ROOT/'analytics')
    run_env['OMP_NUM_THREADS'] = '4'
    run_env['OPENBLAS_NUM_THREADS'] = '4'
    subprocess.run([sys.executable, '-u', '-m', 'bda.experiment', '--root', str(ROOT),
                    '--dataset', str(DATASET), '--output', str(RUN_DIR)], check=True, env=run_env)

checks = json.loads((RUN_DIR/'validation.json').read_text())
environment = json.loads((RUN_DIR/'environment.json').read_text())
assert checks['status'] == 'complete' and checks['nine_algorithms']
assert hashlib.sha256(DATASET.read_bytes()).hexdigest() == environment['dataset_sha256']
if not (RUN_DIR/'figures/atlas_5.png').is_file():
    from bda.extra_figures import build as build_atlas
    build_atlas(RUN_DIR)
print('Mode:', 'fresh training in this execution' if RETRAIN else 'reading completed, verified experiment artifacts')
display(pd.Series({k:v for k,v in environment.items() if k not in ['git_dirty_files','source_sha256']}, name='Recorded environment').to_frame())
display(pd.Series(checks, name='Validation gates').to_frame())''')
    md('''## 4. Load and understand the data

**Unit of analysis:** one generated aggregate observation window, not one packet and not one person.
**Target:** 13 traffic classes, consisting of BENIGN plus 12 attack patterns. Each has 3,000 windows.
The test partition has 450 windows per class. Balanced classes mean attacks comprise 12/13 of the
dataset; this differs sharply from many deployed networks.

Spark performs Parquet loading, exact-row deduplication, validity filtering, null/infinity normalization,
grouped quality checks and feature preparation. A bounded collection is made for local plots and
the four Python estimators. These collections would require redesign for data larger than driver memory.''')
    code('''df = pd.read_parquet(RUN_DIR/'clean_dataset.parquet')
audit = pd.read_csv(RUN_DIR/'column_audit.csv')
quality = json.loads((RUN_DIR/'data_quality.json').read_text())
contract = json.loads((RUN_DIR/'feature_contract.json').read_text())
features, labels = contract['features'], contract['labels']
print(f'{len(df):,} windows | {len(df.columns)} columns | {df.label.nunique()} classes | {len(features)} retained features')
display(df.head(5))
display(df[features].describe().T.round(3))
display(pd.Series(quality, name='Audit finding').to_frame())''')
    for heading, image, text in [
        ('4.1 Class balance and taxonomy', '01_class_distribution', 'Each class has equal support. Accuracy alone can still conceal poor recall for particular classes; macro F1 weights classes equally.'),
        ('4.2 Family, protocol and service context', '02_context_distribution', 'Protocol and application are fixed by scenario definitions here. They are useful for describing the dataset but excluded from the model to reduce scenario shortcuts.'),
        ('4.3 Time and identifier leakage', '03_time_leakage', 'The generator emits class blocks in sequence. Time, sequence and scenario-coded IDs could reveal the label. A chronological split here would also omit entire classes from training; it is not a meaningful deployment test.'),
        ('4.4 Traffic behavior by class', '04_behavior_boxplots', 'Read the median, interquartile range and overlap, not only extreme rates. Log axes are labelled. Similar amplification classes can have overlapping behavior despite distinct labels.'),
        ('4.5 Correlation and redundancy', '05_correlation', 'Packet counts and rates share a formula with fixed window length. Correlated inputs violate naive Bayes independence and can overweight distances in KNN. A correlation is not proof of cause.'),
        ('4.6 Low-rate attacks and overlap', '06_overlap_scatter', 'Slow HTTP can have low packet volume yet high flow pressure. A single packets-per-second threshold is therefore a weak universal attack detector.'),
        ('4.7 Missingness and physical inconsistencies', '09_data_quality', 'The audit preserves synthetic artifacts instead of silently correcting their meaning. Flow table occupancy is clipped; link utilization assumes 1 Gbit/s while old topology prose says 100 Mbit/s. ACK/SYN is not a measured completion fraction.'),
    ]:
        md(f'### {heading}\n\n{text}')
        code(f"show_figure('{image}')")
    md('''### 4.8 Distribution atlas: every retained numeric feature

These five pages cover all 40 inputs. Benign and attack groups are normalized separately,
so their densities can be compared despite the 3,000 versus 36,000 support difference.
All finite values are retained in the plotted ranges. The dictionary gives units and generated
meaning. This is descriptive EDA, not a test-driven feature-selection procedure.''')
    for page in range(1, 6):
        code(f"show_figure('atlas_{page}')")
    md('''## 5. Preprocessing and leakage prevention

1. Remove identifiers, labels/families, synthetic generation controls, scenario protocol/application,
   random switch/site/port identities and the explicit controller CPU proxy.
2. Save a stratified 70% train / 15% validation / 15% test split with seed 42.
3. Assert no row overlap and no identical retained feature vectors across partitions.
4. Determine all-null/constant features from training rows only; drop them.
5. Fit Spark `Imputer(strategy='median')` on training only, followed by `VectorAssembler` and
   `StandardScaler(withMean=True, withStd=True)`. Spark uses sample standard deviation.
6. Reuse the fitted preprocessing unchanged on validation and test. Export the exact medians,
   means and standard deviations and check Python transformation parity.

For $x_j$, standardization is $z_j=(x_j-\\mu_{j,train})/s_{j,train}$.
Do not remove high-rate windows merely because they are outliers; those may be the attacks.
No SMOTE is applied because the current classes are balanced. If future data is imbalanced,
resampling must happen inside the training split only.''')
    code('''display(audit[['column','dtype','missing','unique','use','reason']])
display(audit[audit.column.isin(features)][['column','unit','meaning']])
print('Dropped training constants:', contract['train_constant_columns'])
print('Retained feature order:', features)
stats = json.loads((RUN_DIR/'preprocessing.json').read_text())
display(pd.DataFrame({'feature':features, 'training_median':stats['median'],
                      'training_mean_after_imputation':stats['mean'], 'training_sample_std':stats['std']}))
display(pd.read_csv(RUN_DIR/'split_counts.csv'))
show_figure('07_split_counts')''')
    code("show_figure('00_pipeline')")
    md('''## 6. Spark versus Pandas: measured scope

Python is a language; Pandas and PySpark are different data-processing systems accessed from Python.
Pandas computes locally; Spark builds plans and schedules tasks through a JVM and workers. A Spark
DataFrame transformation is lazy; timing `groupBy` without a completed action would be misleading.

Here both engines read only `label` and `packet_rate` from the same Parquet and compute class counts
and mean packets/s. Three completed trials alternate engine order. Numerical results must agree.
Spark initialization is reported separately. OS caches are not reset; results include warm-cache effects.
This is a small local benchmark, not a test of cluster scalability. Differences among the nine ML
algorithms must not be interpreted as a controlled Spark-versus-scikit-learn estimator comparison.''')
    code('''timings = pd.read_csv(RUN_DIR/'engine_benchmark.csv')
display(timings)
display(timings.groupby('engine').seconds.agg(['min','median','max']))
display(pd.Series(json.loads((RUN_DIR/'spark_runtime.json').read_text())).to_frame('Spark runtime'))
show_figure('08_engine_benchmark')''')
    md('''## 7. Model selection and evaluation rules

Each algorithm receives a small predeclared candidate set. Gaussian NB is a fixed baseline.
The best candidate per algorithm is chosen by validation macro F1. The overall model is also selected
by validation macro F1, and this decision is saved before test evaluation. Test ranks are descriptive.
The chosen models remain trained on 70% of rows; there is no hidden train+validation refit.

For each class, $Precision=TP/(TP+FP)$, $Recall=TP/(TP+FN)$ and
$F1=2PR/(P+R)$. Macro averages give each of 13 classes the same weight; weighted F1 uses class support.
Accuracy is total correct divided by total windows. A dummy classifier predicting one class has
accuracy 1/13 on this balanced data; it is a baseline reference and is not counted among the nine.

Fit times cover the selected candidate only. Prediction timing is the median of three completed
5,850-row batches after a warmup. Spark timing includes scheduling and collection; scaling is excluded
for both engines because vectors are prepared. Amortized batch milliseconds per row are **not**
single-request latency or a full controller response time. The fixed random seeds improve reproducibility;
hardware and numeric backend differences can still affect floating-point details and timing.''')
    code('''metrics = pd.read_csv(RUN_DIR/'model_metrics.csv')
per_class = pd.read_csv(RUN_DIR/'per_class_metrics.csv')
tuning = pd.read_csv(RUN_DIR/'tuning_results.csv')
selection = json.loads((RUN_DIR/'selection.json').read_text())
winner = selection['winner']
print('Validation-selected model:', winner)
display(tuning[['model','engine','candidate','validation_macro_f1','fit_seconds']].round(5))
display(metrics[['model','engine','validation_macro_f1','accuracy','precision_macro','recall_macro','f1_macro','f1_weighted','f1_ci_low','f1_ci_high']].round(5))
show_figure('10_model_comparison')''')
    md('''**Uncertainty:** the macro F1 intervals use 200 stratified bootstrap resamples of the fixed test
population. They quantify sampling variation within the existing synthetic distribution, not generator
validity, domain shift, independent-session generalization or training-seed variation.''')
    wanted = [name for name, record in ALGORITHMS.items() if person is None or record[0] == person]
    for index, name in enumerate(wanted, 1):
        member, engine, theory = ALGORITHMS[name]
        md(f'## 8.{index} {name}\n\n**Presenter:** {member}. **Training backend:** {engine}.\n\n{theory}')
        code(f'''name = {name!r}
display(tuning[tuning.model == name].drop(columns='parameters').round(5))
print('Selected settings:')
display(pd.Series(selection['models'][name]['parameters'], dtype=object).to_frame('Value'))
display(metrics[metrics.model == name].T)
display(per_class[per_class.model == name].drop(columns='model').round(4))
model_row = metrics[metrics.model == name].iloc[0]
weak = per_class[per_class.model == name].nsmallest(3, 'recall')
display(Markdown(f"**Measured inference:** test macro F1 **{{model_row.f1_macro:.4f}}**, accuracy **{{model_row.accuracy:.2%}}**. "
                 f"The lowest-recall classes are **{{', '.join(weak['class'])}}**. Inspect their off-diagonal errors below."))
show_figure('cm_' + name.lower().replace(' ', '_'))''')
        md('''**How to explain this result in the viva:** identify one strong class, one weak class and
its most frequent confusion. Connect that behavior to the algorithm's assumptions and the observed
feature overlap. A weak model is a valid finding; do not change the split just to improve its score.
Use the target label as a diagnostic category, then separately examine whether the model missed
an attack entirely or merely predicted a different attack type.''')
    md('''## 9. Cross-model comparison and error analysis

The recall heatmap exposes class-level failures that aggregate accuracy can hide. Rows are true classes.
In confusion matrices, diagonal mass is correct classification; off-diagonal mass is confusion.
A wrong amplification subtype can still be a correct binary attack alert. BENIGN→attack causes false
alarms; attack→BENIGN is a missed attack. Those errors deserve separate treatment.''')
    code("show_figure('12_recall_heatmap')\nshow_figure('18_error_pairs')")
    md('''### 9.1 Compute and serving tradeoffs

Choose on validation quality subject to resource requirements. This benchmark does not impose a
measured controller latency budget. A per-row batch average below one millisecond does not prove
line-rate packet classification. The system classifies aggregate windows and must wait for collection,
feature construction, transport, scheduling, inference and policy enforcement.''')
    code("display(metrics[['model','fit_seconds','prediction_batch_seconds','amortized_prediction_ms']].round(5))\nshow_figure('11_runtime')\nshow_figure('14_tradeoff')")
    md('''### 9.2 Feature relevance and confidence

Impurity importance describes the fitted tree models. It is not a causal ranking and can be split across
redundant counters. A top-class confidence plot compares predicted confidence with observed correctness
in bins. It is descriptive only: no calibrator or decision rule is tuned on test outcomes.''')
    code("show_figure('15_feature_importance')\nshow_figure('16_reliability')")
    md('''## 10. Turning class predictions into operational evidence

For probability-producing models, attack score is $1-P(BENIGN)$, a model estimate rather than a measured
attack probability. For SVM, use the negative benign margin as a ranking score. ROC and precision-recall
curves assess this binary question separately from 13-class classification.

For every model, select a threshold using validation data: maximize attack recall subject to at most
1% benign false alarms on that validation set. Freeze it, then report test false alarms and missed attacks.
With only 450 benign validation windows, a 1% requirement is coarse; it is not a deployment guarantee.
The balanced synthetic dataset's high attack prevalence can make PR results look very favorable.''')
    code('''operations = json.loads((RUN_DIR/'operating_points.json').read_text())
display(pd.DataFrame(operations).T)
display(metrics[['model','attack_recall_argmax','benign_fpr_argmax','attack_roc_auc','attack_average_precision','tn','fp','fn','tp']].round(5))
show_figure('13_roc_pr')
show_figure('17_prevalence')
display(pd.read_csv(RUN_DIR/'prevalence_scenarios.csv').query('model == @winner'))''')
    md('''### 10.1 Output contract and policy example

A useful prediction record contains **window ID, model/version, feature-schema version, predicted class,
attack score, score type, validation-selected threshold, timestamp and routing context**. Keep switch/port
identity for routing the alert; it was excluded from learned features. The current example table carries
available offline context and is not a complete live telemetry event implementation.

Suggested flow: aggregate telemetry → validate schema → apply saved preprocessing → run saved model →
produce score and class → request corroborating per-flow telemetry → alert or temporarily rate-limit
specific verified traffic according to policy. Escalate repeated, corroborated high-risk windows with
expiry and rollback. A class label alone cannot identify the offending flow or safely justify blocking
an entire shared ingress port. This notebook sends no controller commands.

The saved examples deliberately include errors where available. A confident wrong subtype is a reason
to inspect evidence, not to invent a more precise enforcement rule.''')
    code("examples = pd.read_csv(RUN_DIR/'inference_examples.csv')\ndisplay(examples)")
    md('''### 10.2 Reusing the saved estimator

Spark models are stored as native `.spark` directories; Python models use `.joblib` files.
The fitted Spark preprocessing is saved independently, along with a portable numeric transform.
`feature_contract.json` preserves feature order and the numeric-index-to-label mapping.
Always run the saved preprocessing; fitting a new scaler at inference changes the model input space.
The selected estimator was reloaded and checked against all held-out predictions.

For an unseen batch containing the required feature columns:
```python
from bda.serving import Predictor
predictor = Predictor(RUN_DIR)  # starts Spark only for a Spark-selected estimator
output = predictor.predict(new_windows)
predictor.close()
```
Missing required columns fail with a clear schema error; present null cells use saved training medians.
Scores are estimates within the training distribution. New capture feature definitions must match the
contract or trigger retraining rather than silently reuse an incompatible estimator.''')
    code('''from bda.serving import Predictor
predictor = Predictor(RUN_DIR)
try:
    inference = predictor.predict(df.sample(5, random_state=42))
    display(inference)
finally:
    predictor.close()''')
    md('''## 11. Three-person presentation split

| Member | Algorithms | Shared responsibility |
|---|---|---|
| Satya | Logistic Regression, Decision Tree, Random Forest | dataset validity, Spark pipeline, validation selection |
| Prithvi | Gaussian Naive Bayes, MLP, RBF SVM | assumptions, scaling, probabilities versus margins |
| Roydon | KNN, Extra Trees, Histogram Gradient Boosting | runtime, error analysis, inference and alert policy |

For each algorithm explain: input vector → training mechanism → prediction mechanism → validation
choice → test result → weakest class → runtime cost → appropriate output use. Everyone should be able
to explain the shared split and why this synthetic experiment cannot establish real deployment quality.''')
    md('''## 12. Final findings and next experiment

The following text is computed from executed artifacts rather than filled in before training.''')
    code('''selected = metrics[metrics.model == winner].iloc[0]
worst = per_class[per_class.model == winner].nsmallest(3,'recall')
bench = timings.groupby('engine').seconds.median()
display(Markdown(f"The validation-selected model is **{winner}** (validation macro F1 **{selected.validation_macro_f1:.4f}**). "
                 f"Its fixed test macro F1 is **{selected.f1_macro:.4f}**, accuracy **{selected.accuracy:.2%}**. "
                 f"The lowest-recall test classes are **{', '.join(worst['class'])}**. "
                 f"Median completed aggregation time: Pandas **{bench['Pandas']:.3f}s**, Spark **{bench['Spark']:.3f}s**, "
                 "excluding Spark startup. These measurements apply to this machine and this synthetic dataset."))''')
    md('''**What remains:** independent packet/flow-derived measured telemetry with repeated capture sessions,
diverse benign services, no hardcoded-zero controller observations masquerading as measurements,
verified counter/feature units, session-separated testing, drift and calibration evaluation, realistic
attack prevalence, and full telemetry-to-controller latency/false-alarm measurement. The newer
`sdn_ddos` capture project remains separate; phase 2 supplies the improved dataset before retraining.

**Authoritative references and what to read:**
- [Spark classification guide](https://spark.apache.org/docs/3.5.6/ml-classification-regression.html):
  algorithm assumptions, multiclass support and prediction outputs. Map these to the five Spark estimators.
- [Spark feature guide](https://spark.apache.org/docs/3.5.6/ml-features.html): `Imputer`, `VectorAssembler`,
  `StandardScaler`; understand fitted statistics and transformer reuse.
- [scikit-learn common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html): split before fitting
  transformations; identify leakage in an apparently successful notebook.
- [scikit-learn ensemble guide](https://scikit-learn.org/stable/modules/ensemble.html): Extra Trees and
  histogram boosting; distinguish randomized independent trees from sequential corrections.
- [SVC API](https://scikit-learn.org/stable/modules/generated/sklearn.svm.SVC.html): margins,
  multiclass strategy, `C`, `gamma`, and the extra cost/meaning of probability estimation.

All saved tables, figures and prediction files belong to the run ID and dataset hash shown above.
The read-only artifact-review mode reuses those results explicitly; a new training run creates a new run ID.''')
    nb = nbf.v4.new_notebook(cells=cells)
    nb.metadata = {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                   'language_info': {'name': 'python', 'version': '3.12'}}
    nbf.validate(nb)
    name = '05_lab_evaluation_2_nine_models.ipynb' if person is None else f'{dict(Satya="24063",Prithvi="24076",Roydon="24059")[person]}_{person}_LA2.ipynb'
    target = DEST / name
    nbf.write(nb, target)
    print(target, len(cells), 'cells')


if __name__ == '__main__':
    for person in [None, 'Satya', 'Prithvi', 'Roydon']:
        build(person)
