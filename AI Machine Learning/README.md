# churn-ml: end-to-end customer churn ML platform

A production-style machine learning system that predicts which subscription customers will leave
in the next 8 weeks, explains why, decides who should get a retention offer, and watches itself
for drift. It covers the full lifecycle:

```
simulate ─► validate ─► point-in-time features ─► out-of-time split (with embargo)
   ─► Optuna tuning × 5 model families (incl. PyTorch) ─► blended ensemble ─► calibration
   ─► profit-optimal threshold ─► champion/challenger ─► model registry ─► HTML report + MLflow
   ─► batch scoring with SHAP reasons ─► drift monitoring (global + per segment) ─► REST API
```

## Results (default profile, one full run, about 6 minutes on 6 CPU cores)

| | Value |
|---|---|
| Data | 16,293 customers · 860k weekly usage rows · 216k invoices · 84k support tickets |
| Rows | 96.6k train (12 snapshots) · 14.8k validation · 14.9k test, each a later period |
| Test ROC AUC (final ensemble) | **0.772** (best single model 0.770) |
| Lift in top 10% | **3.9×** (39% of churners are in the riskiest 10% of customers) |
| Calibration error (ECE) | **0.0065** |
| Campaign profit on test | **$114k**, vs $44k for offering everyone the deal |
| Drift check at week 104 | alert: `region=west` sessions trend PSI 0.80 (the simulated competitor launch) |

Churn is noisy by nature. Part of the 8-week future can't be predicted from the past, so an AUC
around 0.77 is realistic, not a ceiling the code imposes.

## What's inside

| Area | Module | Highlights |
|---|---|---|
| Synthetic world | `data/simulator.py` | Each customer has a hidden satisfaction level that moves with outages, price rises, promo expiry, slow ticket handling and a competitor launch. Includes a "considering leaving" phase. Produces usage, billing and free-text tickets. |
| Data quality | `data/validation.py` | Raw-table integrity checks (orphans, no events after churn, value ranges) and the feature contract (schema, infinities, negative counts, unseen categories). |
| Kernels | `kernels.py`, `_native` engine, `_kernels_py.py` | Group-by and histogram kernels behind feature building and drift checks: a bundled compiled engine with a NumPy fallback (see [docs/native-kernels.md](docs/native-kernels.md)). |
| Features | `features/` | 36 model inputs built point-in-time from rolling windows, trends, recency, billing and ticket signals, plus TF-IDF → SVD embeddings of ticket text. A test proves no future leakage. |
| Splits | `training/splits.py` | Out-of-time train/validation/test with an **embargo**: a snapshot is used only once its label window has closed. |
| Models | `models/zoo.py`, `models/neural.py` | Logistic regression, random forest, LightGBM, XGBoost and a **PyTorch tabular network** with categorical embeddings, BatchNorm and early stopping, wrapped as a scikit-learn estimator. |
| Tuning | `training/tuning.py` | Optuna TPE search per model on a stratified subsample. Preprocessing is fitted once per encoding and reused across trials. Studies are stored in SQLite. |
| Ensemble + calibration | `models/calibration.py` | Blend weights that minimize log loss (softmax-parameterized), then isotonic or Platt calibration on the validation period. |
| Decision policy | `training/metrics.py` | Threshold that maximizes campaign profit (offer cost, success rate, customer value), plus risk tiers and expected revenue at risk. |
| Registry | `registry/model_registry.py` | Versioned bundles, staging/production/archived stages, champion vs challenger on the same out-of-time data, promotion, rollback, atomic writes. |
| Explainability | `explain/shap_explainer.py` | TreeSHAP on the strongest tree member, aggregated back to readable input features (one-hot columns and text components merged). |
| Monitoring | `monitoring/drift.py` | PSI plus KS test per feature, prediction drift, and **segment-level drift** (a shock in one region is invisible in global numbers). |
| Reporting | `reporting/` | Self-contained HTML training and drift reports: leaderboard, ROC/PR, calibration, gains, profit curves, SHAP. |
| Tracking | `training/tracking.py` | MLflow parameters, metrics and artifacts (SQLite backend); a no-op when disabled. |
| Serving | `serving/` | FastAPI app with a request schema generated from the feature spec, live scoring from the data store, explanations, a drift endpoint, hot reload and Prometheus metrics. |

## Setup

**Python version: use CPython 3.14.** The bundled native engine (`src/churn_ml/_native/`) is built
for CPython 3.14 on Windows x64 and Linux x86_64. Other Python versions (3.10+) work, but run on the
slower NumPy kernels instead.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[dev,native]"
python scripts/build_native.py --if-present   # build churn_ml._kernels_ext when its source exists
```

> **Windows note.** Recent PyTorch wheels need a newer Microsoft C++ runtime than older Windows
> Server images ship with. The `msvc-runtime` dependency puts current DLLs in the venv, and
> `churn_ml/_runtime.py` preloads them before torch is imported. The system itself isn't changed.

## Usage

```powershell
churn-ml pipeline                  # everything: simulate → train → score → monitor (~6 min)
churn-ml -c fast pipeline          # small profile, about 30 s

churn-ml simulate                  # raw tables -> artifacts/raw/*.parquet
churn-ml features                  # cached, fingerprinted training snapshots
churn-ml train --open              # tune, ensemble, calibrate, register; opens the HTML report
churn-ml score --week 104          # ranked CSV with risk tier, offer flag and SHAP reasons
churn-ml monitor --open            # drift report; --fail-on-alert exits 2 (for schedulers/CI)
churn-ml models                    # registry table
churn-ml promote 3 / rollback      # stage management
churn-ml serve                     # http://127.0.0.1:8000/docs

# any config value can be overridden:
churn-ml train --set tuning.n_trials.lightgbm=80 --set models.enabled=[lightgbm,tabular_nn]
mlflow ui --backend-store-uri sqlite:///artifacts/mlflow.db
```

### API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health`, `/model` | Status, production version, test metrics, feature schema |
| POST | `/predict?explain=true` | Score engineered feature records (strictly validated) |
| POST | `/customers/score` | `{"customer_ids": [...], "as_of_week": 104, "explain": true}`: builds features from the store |
| POST | `/drift` | Drift report for a batch of records (50 or more) |
| POST | `/admin/reload` | Hot-swap to the current production model |
| GET | `/metrics` | Prometheus text format: request counts and latency, predictions, model version |

### Docker

```bash
docker compose --profile jobs run --rm trainer   # train into the shared volume
docker compose up -d api mlflow                  # :8000 API, :5000 MLflow UI
```

## Native kernels

Feature building and drift checks run on six group-by and histogram kernels behind
[`src/churn_ml/kernels.py`](src/churn_ml/kernels.py). Three backends implement the same API:

| Backend | Module | |
|---|---|---|
| `ext` | `churn_ml._kernels_ext` | built from source with `python scripts/build_native.py` (planned) |
| `native` | `churn_ml._native` | bundled pre-built engine package (binary-only, **CPython 3.14**): Windows x64 `.pyd` and Linux x86_64 `.so` |
| `numpy` | `churn_ml._kernels_py` | pure NumPy; the behavioral specification |

The first that imports is used (`ext`, then `native`, then `numpy`); `CHURN_ML_KERNELS=ext|native|numpy`
forces one. Design and function contract: **[docs/native-kernels.md](docs/native-kernels.md)**.
Open work items: **[TASKS.md](TASKS.md)**.

```powershell
python scripts/build_native.py           # build churn_ml._kernels_ext from src/churn_ml/_kernels_ext.pyx
python scripts/benchmark_native.py       # ext vs native engine vs numpy
pytest tests/test_kernels.py             # every backend vs NumPy and pandas
```

## Configuration

`configs/default.yaml` is the full-scale profile. `configs/fast.yaml` merges over it for quick
runs. Settings are validated by pydantic (`settings.py`). Key settings: simulation size and drift
scenario, label horizon, feature windows, enabled models and trial budgets, calibration method,
business economics, promotion tolerance, PSI thresholds and the drift segment column.

## Tests

```powershell
pytest                 # 70 tests, about 35 s (trains real models on the fast profile)
pytest -m "not slow"   # unit tests only
ruff check src tests
```

The tests cover kernel equivalence (every available backend vs NumPy and pandas), leakage (features are unchanged when future data is removed), label correctness,
data contracts, the neural network (learning, unseen categories, pickling), calibration and
blending, profit math checked by hand, the split embargo, drift detection (global, categorical,
segment, prediction), registry promotion and rollback, champion vs challenger rejecting a worse
model, scoring, and every API endpoint.

## Project layout

```
configs/                 default.yaml, fast.yaml
src/churn_ml/
  data/                  simulator, validation
  features/              spec (single source of feature names), point-in-time builder
  models/                preprocessing, zoo, PyTorch net, calibration/blending, ChurnModel bundle
  training/              dataset cache, splits, tuning, metrics, tracking, trainer
  registry/              versioned file-based model registry
  explain/               SHAP explainer
  monitoring/            drift profiles and reports
  reporting/             charts + Jinja templates
  serving/               FastAPI app and schemas
  _native/               bundled native engine: compiled submodules (_aggregate, _select, _counting,
                         _text, _binning) for CPython 3.14 on Windows x64 and Linux x86_64
  kernels.py             kernel dispatch: _kernels_ext -> _native engine -> _kernels_py (NumPy)
  scoring.py             batch scoring and monitoring jobs
  cli.py                 churn-ml command
docs/                    native-kernels.md
scripts/                 build_native.py, benchmark_native.py
benchmarks/              engine_baseline.json
tests/                   unit + end-to-end tests
artifacts/               generated: raw data, features, registry, predictions, monitoring, mlflow.db
```
