"""Candidate model families with defaults and Optuna search spaces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import optuna

from ..features.spec import FeatureSpec
from .preprocessing import Encoding

HIDDEN_CHOICES = {"128-64": (128, 64), "256-128": (256, 128), "256-128-64": (256, 128, 64), "512-256": (512, 256)}


@dataclass(frozen=True)
class ModelSpec:
    name: str
    encoding: Encoding
    is_tree: bool
    factory: Callable[[dict[str, Any], FeatureSpec, int], Any]
    space: Callable[[optuna.Trial], dict[str, Any]]


def _logistic(params, spec, seed):
    from sklearn.linear_model import LogisticRegression

    return LogisticRegression(max_iter=3000, random_state=seed, **params)


def _logistic_space(trial):
    return {"C": trial.suggest_float("C", 1e-3, 10.0, log=True)}


def _forest(params, spec, seed):
    from sklearn.ensemble import RandomForestClassifier

    return RandomForestClassifier(n_jobs=-1, random_state=seed, **params)


def _forest_space(trial):
    return {
        "n_estimators": trial.suggest_int("n_estimators", 150, 400, step=50),
        "max_depth": trial.suggest_int("max_depth", 6, 18),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 5, 80, log=True),
        "max_features": trial.suggest_categorical("max_features", ["sqrt", 0.3, 0.5]),
    }


def _lightgbm(params, spec, seed):
    from lightgbm import LGBMClassifier

    return LGBMClassifier(random_state=seed, n_jobs=-1, verbose=-1, subsample_freq=1, **params)


def _lightgbm_space(trial):
    return {
        "n_estimators": trial.suggest_int("n_estimators", 200, 1200, step=100),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 15, 127, log=True),
        "min_child_samples": trial.suggest_int("min_child_samples", 20, 300, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 1.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
    }


def _xgboost(params, spec, seed):
    from xgboost import XGBClassifier

    return XGBClassifier(random_state=seed, n_jobs=-1, tree_method="hist", eval_metric="logloss", **params)


def _xgboost_space(trial):
    return {
        "n_estimators": trial.suggest_int("n_estimators", 200, 1000, step=100),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 9),
        "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 30.0, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 1.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
    }


def _neural(params, spec, seed):
    from .neural import TabularNNClassifier

    params = dict(params)
    hidden = params.pop("hidden", "256-128")
    return TabularNNClassifier(
        n_categorical=len(spec.categorical), hidden_sizes=HIDDEN_CHOICES[hidden], random_state=seed, **params
    )


def _neural_space(trial):
    return {
        "hidden": trial.suggest_categorical("hidden", list(HIDDEN_CHOICES)),
        "dropout": trial.suggest_float("dropout", 0.0, 0.4),
        "lr": trial.suggest_float("lr", 3e-4, 3e-3, log=True),
        "weight_decay": trial.suggest_float("weight_decay", 1e-6, 1e-3, log=True),
        "batch_size": trial.suggest_categorical("batch_size", [256, 512, 1024]),
    }


MODEL_SPECS: dict[str, ModelSpec] = {
    "logistic_regression": ModelSpec("logistic_regression", "onehot", False, _logistic, _logistic_space),
    "random_forest": ModelSpec("random_forest", "onehot", True, _forest, _forest_space),
    "lightgbm": ModelSpec("lightgbm", "onehot", True, _lightgbm, _lightgbm_space),
    "xgboost": ModelSpec("xgboost", "onehot", True, _xgboost, _xgboost_space),
    "tabular_nn": ModelSpec("tabular_nn", "ordinal", False, _neural, _neural_space),
}


def get_model_spec(name: str) -> ModelSpec:
    try:
        return MODEL_SPECS[name]
    except KeyError:
        raise ValueError(f"Unknown model {name!r}; choose from {sorted(MODEL_SPECS)}") from None
