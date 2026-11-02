"""Optuna hyper-parameter search on pre-transformed matrices.

Preprocessing has no tuned parameters, so each encoding is fitted once and
reused across every trial; trials only refit the estimator.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import optuna

from ..features.spec import FeatureSpec
from ..logging_utils import get_logger
from ..models.zoo import get_model_spec
from ..settings import TuningConfig
from .metrics import score_for_tuning

log = get_logger(__name__)
optuna.logging.set_verbosity(optuna.logging.WARNING)


@dataclass
class TuningResult:
    model: str
    best_params: dict[str, Any]
    best_score: float
    n_trials: int
    seconds: float
    history: list[dict[str, Any]] = field(default_factory=list)


def _subsample(X: np.ndarray, y: np.ndarray, rows: int | None, seed: int):
    if rows is None or len(y) <= rows:
        return X, y
    rng = np.random.default_rng(seed)
    pos, neg = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
    take_pos = int(round(rows * len(pos) / len(y)))
    idx = np.concatenate([rng.choice(pos, take_pos, replace=False), rng.choice(neg, rows - take_pos, replace=False)])
    rng.shuffle(idx)
    return X[idx], y[idx]


def tune(
    name: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    spec: FeatureSpec,
    cfg: TuningConfig,
    seed: int,
    storage: str | None = None,
    study_prefix: str = "churn",
) -> TuningResult:
    model_spec = get_model_spec(name)
    n_trials = cfg.n_trials.get(name, 10)
    X_fit, y_fit = _subsample(X_train, y_train, cfg.sample_rows, seed)
    start = time.perf_counter()

    def objective(trial: optuna.Trial) -> float:
        params = model_spec.space(trial)
        estimator = model_spec.factory(params, spec, seed)
        estimator.fit(X_fit, y_fit)
        return score_for_tuning(cfg.metric, y_val, estimator.predict_proba(X_val)[:, 1])

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=seed, multivariate=True),
        study_name=f"{study_prefix}-{name}",
        storage=storage,
        load_if_exists=False,
    )
    study.optimize(objective, n_trials=n_trials, timeout=cfg.timeout_seconds, gc_after_trial=True)
    seconds = time.perf_counter() - start
    history = [
        {"number": t.number, "value": t.value, **t.params}
        for t in study.trials
        if t.state == optuna.trial.TrialState.COMPLETE
    ]
    log.info(
        "tuned %-20s best %s=%.4f after %d trials (%.0fs)", name, cfg.metric, study.best_value, len(history), seconds
    )
    return TuningResult(name, dict(study.best_params), float(study.best_value), len(history), seconds, history)
