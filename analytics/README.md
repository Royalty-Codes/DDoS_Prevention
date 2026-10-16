# Big Data Analytics — Lab Evaluation 2

Open `05_lab_evaluation_2_nine_models.ipynb` for the complete experiment.
The team notebooks explain three algorithms each while retaining the shared
data audit, preprocessing, comparison and inference sections:

- `24063_Satya_LA2.ipynb`: Logistic Regression, Decision Tree, Random Forest.
- `24076_Prithvi_LA2.ipynb`: Gaussian Naive Bayes, MLP, RBF SVM.
- `24059_Roydon_LA2.ipynb`: KNN, Extra Trees, Histogram Gradient Boosting.

This phase deliberately uses only the archived **original synthetic 39,000-row,
63-column, 13-class** dataset requested for the first ML comparison. It does not
merge that schema with the newer measured `sdn_ddos` capture pipeline or the old
110,000-row capture used by the LA1 reference notebooks. Retraining on an improved
measured dataset is a later experiment with its own feature contract and splits.

## Run on Linux / WSL

Use Java 17 and Python 3.12. From the repository root:

```bash
python3.12 -m venv .venv-bda
source .venv-bda/bin/activate
python -m pip install -r analytics/requirements-bda.txt
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PYTHONPATH="$PWD/analytics"
export OMP_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
python -m unittest discover -s analytics/tests -v
python -u -m bda.experiment \
  --root "$PWD" \
  --dataset archive/legacy-2026-09-22/data/processed/sdn_ddos_versatile.parquet \
  --output artifacts/bda/lab2-synthetic-seed42
python -m bda.verify artifacts/bda/lab2-synthetic-seed42
```

Native Windows Spark can require additional Hadoop binaries for saving models.
The supported local reproduction path for this project is Linux/WSL; do not
treat a successful `spark.range().count()` as proof that model persistence works.

For a new experiment, use a new output directory. The source commit, dirty-file
status, source hashes, package versions, seed, feature order, split IDs, dataset
SHA256 and hardware/backend are recorded. The source implementation is reusable;
the notebooks explain and call it rather than contain a second training pipeline.

## Open or rerun notebooks

```bash
python analytics/build_bda_notebooks.py
python -m jupyter nbconvert --execute --to notebook --inplace \
  analytics/05_lab_evaluation_2_nine_models.ipynb
```

If the run is complete, notebook execution explicitly reads the verified saved
artifacts and does not silently repeat fitting. To train again through a notebook:

```bash
export BDA_RETRAIN=1
export BDA_RUN_ID=lab2-synthetic-new-run
```

Cloud notebook setup clean-clones only its own marked disposable directory and
checks out `BDA_REVISION` (default `bda-nine-models`). Set that environment variable
to a commit for exact reproduction. Colab uses mounted Drive for results and can
upload the original Parquet once. Kaggle uses `/kaggle/working`; save a version
with outputs to retain them. Data is not assumed to be present in the Git remote.
CPU is the intended backend; the same interface detects Local, Colab and Kaggle.
GPU/TPU availability does not accelerate these selected Spark/scikit-learn models.

## What is saved per run

- `model_metrics.csv`: nine validation-selected models and untouched-test reporting.
- `tuning_results.csv`, `selection.json`: candidate settings and validation selection.
- `per_class_metrics.csv`, `confusion_*.csv`: class-level precision, recall, F1 and errors.
- `operating_points.json`: validation-frozen attack thresholds and test false alarms.
- `predictions/*.parquet`: every held-out prediction and attack score.
- `split_manifest.csv`, `feature_contract.json`, `preprocessing.json`: reusable contracts.
- `preprocessor.spark`, `models/*`: native Spark pipelines/models and Python estimators.
- `data_quality.json`, `column_audit.csv`: data provenance, exclusions and limitations.
- `engine_benchmark.csv`: equivalent completed Parquet aggregation trials with parity checks.
- `inference_examples.csv`, `prevalence_scenarios.csv`: operational examples and labelled scenarios.
- `figures/*.png`: portable static notebook plots.
- `environment.json`, `spark_runtime.json`, `validation.json`: reproducibility and checks.

## Honest interpretation

The candidate search is intentionally small and predeclared. Gaussian NB is a
fixed baseline; the other algorithms compare two settings. There is no claim
that these are globally optimal hyperparameters. Validation chooses the overall
model before test results are exposed. Historical results on the same generator
mean this is not a pristine independent test population.

No prediction sends a switch command. Batch milliseconds per row are not
single-request latency, packet processing rate or end-to-end mitigation time.
Synthetic separability and missing benign-service diversity limit real-network
claims, even if attack recall is high. See the notebook and `BDA_PLAN.md` for the
experiment design and the measured-dataset requirements for the next phase.
