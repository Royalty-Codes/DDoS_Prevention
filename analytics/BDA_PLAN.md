# Lab Evaluation 2: nine-model SDN DDoS experiment

## Objective and acceptance criteria
Train nine distinct supervised algorithms on the existing complete 39,000-row,
63-column, 13-class synthetic dataset. Deliver an executed teaching notebook,
per-class and aggregate metrics, plots, persisted models, example inference,
and a three-person presentation guide. Dataset regeneration is phase 2.

## Method and constraints
- Existing architecture and generator remain intact. New code lives in `analytics/bda`.
- Spark local mode performs loading, cleaning, quality checks, aggregation,
  train-only imputation/scaling, and five model fits. Four additional algorithms
  use scikit-learn after an explicit bounded collection to the driver.
- Nine algorithms: multinomial logistic regression, decision tree, random forest,
  Gaussian naive Bayes, multilayer perceptron (Spark); KNN, RBF SVM, Extra Trees,
  histogram gradient boosting (scikit-learn). No dummy model is counted among nine.
- One fixed, saved, stratified 70/15/15 split; all algorithms use identical rows.
- Exclude labels, scenario tags, generation parameters, ordered time identifiers,
  host/switch identities, port identifiers, protocol/application scenario constants,
  and the explicitly named CPU proxy. Keep measured-style numeric telemetry only.
- Learn medians, variance and means on training rows only. Constant training
  columns are removed. Extreme finite values are retained, since attacks are outliers.
- Two predeclared candidate settings per algorithm selected by validation macro F1;
  Gaussian naive Bayes is a fixed analytical baseline with one candidate.
  Freeze each candidate and the overall winner before exposing test performance.
- Report all nine on test, without choosing the deployed model from test rankings.
- Attack score = 1 - P(BENIGN); SVM uses a margin score and does not claim calibrated
  probabilities. Select an operating threshold using validation benign false alarms.
- Accuracy, macro/weighted F1, precision, recall, class recall, confusion matrices,
  attack recall, benign FPR, ROC/PR, fit/predict wall time, and bootstrap intervals.
- Spark/Pandas benchmark uses equivalent completed read+aggregate workloads and
  checks numerical parity; startup is reported separately. No cluster scalability claim.
- Synthetic generator shortcuts and historical test exposure are explicit limitations.
  This is a fresh implementation, not a newly collected independent test population.

## Modules, ownership and gates
| Module | Inputs | Outputs | Dependencies | Owner | Acceptance |
|---|---|---|---|---|---|
| Audit/clean | Existing Parquet | Quality report, clean frame, schema | Spark | Codex | Counts reconcile; no invalid features |
| Split/preprocess | Clean frame | Manifest, fitted preprocessing, vectors | Audit | Codex, explain in notebook | No row overlap; train-only statistics |
| Train/select | Train + validation | Nine fitted models + tuning records | Preprocess | Codex, explain each algorithm | Nine models; no test-driven selection |
| Evaluate/use | Frozen models + test | Metrics, predictions, decision examples | Training | Codex | Independent metric and reload checks |
| Notebook/visuals | Data + experiment artifacts | Executed notebook, HTML, PNGs | Evaluation | Codex | Top-to-bottom execution; visual inspection |
| Presentation | Verified results | Three-person guide | All | Codex | Exactly three algorithms per member |

## Reproduction
Use Python 3.12, Java 17 and `analytics/requirements-bda.txt`. CPU is sufficient;
GPU and TPU do not accelerate these Spark/scikit-learn implementations.
The notebook detects Local/Colab/Kaggle and records commit, dirty state, dataset
SHA256, configuration, package versions, seeds and hardware. Remote notebook setup
uses a marked, disposable checkout and an explicit results destination outside it.
The existing Git remote remains the source of truth; publish changes on a feature
branch if authentication allows it. Never overwrite a user's uncommitted work.
