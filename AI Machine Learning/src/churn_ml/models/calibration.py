"""Post-hoc probability calibration and ensemble blending."""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.special import logit, softmax
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

_EPS = 1e-6


class ProbabilityCalibrator:
    """Maps raw scores to calibrated probabilities (isotonic, Platt/sigmoid, or identity)."""

    def __init__(self, method: str = "isotonic"):
        if method not in {"isotonic", "sigmoid", "none"}:
            raise ValueError(f"unknown calibration method {method!r}")
        self.method = method
        self._model = None

    def fit(self, scores: np.ndarray, y: np.ndarray) -> ProbabilityCalibrator:
        scores, y = np.asarray(scores, dtype=float), np.asarray(y, dtype=float)
        if self.method == "isotonic":
            self._model = IsotonicRegression(y_min=_EPS, y_max=1 - _EPS, out_of_bounds="clip").fit(scores, y)
        elif self.method == "sigmoid":
            z = logit(np.clip(scores, _EPS, 1 - _EPS)).reshape(-1, 1)
            self._model = LogisticRegression(C=1e6).fit(z, y)
        return self

    def transform(self, scores: np.ndarray) -> np.ndarray:
        scores = np.asarray(scores, dtype=float)
        if self.method == "isotonic":
            return self._model.predict(scores)
        if self.method == "sigmoid":
            z = logit(np.clip(scores, _EPS, 1 - _EPS)).reshape(-1, 1)
            return self._model.predict_proba(z)[:, 1]
        return scores


def blend(scores: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray:
    return sum(weights[name] * np.asarray(scores[name], dtype=float) for name in weights)


def optimise_blend_weights(scores: dict[str, np.ndarray], y: np.ndarray) -> dict[str, float]:
    """Non-negative weights summing to one that minimise log loss (softmax parameterisation)."""
    names = list(scores)
    if len(names) == 1:
        return {names[0]: 1.0}
    matrix = np.column_stack([np.clip(scores[n], _EPS, 1 - _EPS) for n in names])
    y = np.asarray(y, dtype=float)

    def loss(z):
        p = np.clip(matrix @ softmax(z), _EPS, 1 - _EPS)
        return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))

    result = minimize(loss, np.zeros(len(names)), method="L-BFGS-B")
    weights = softmax(result.x)
    return {n: float(w) for n, w in zip(names, weights)}
