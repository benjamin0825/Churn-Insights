"""The deployable model bundle: base pipelines + blend + calibration + decision policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from ..data.validation import validate_features
from ..features.spec import ID_COLUMNS, VALUE_COLUMN, FeatureSpec
from ..monitoring.drift import DriftProfile
from .calibration import ProbabilityCalibrator, blend

RISK_TIERS = ("low", "medium", "high")


@dataclass
class ChurnModel:
    pipelines: dict[str, Pipeline]
    weights: dict[str, float]
    calibrator: ProbabilityCalibrator
    threshold: float
    spec: FeatureSpec
    risk_cutoffs: tuple[float, float]
    months_of_value: float
    drift_profile: DriftProfile | None = None
    explainer_model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------- scoring
    def prepare(self, df: pd.DataFrame, validate: bool = True) -> pd.DataFrame:
        frame = df.copy()
        if self.spec.text not in frame:
            frame[self.spec.text] = ""
        frame[self.spec.text] = frame[self.spec.text].fillna("").astype(str)
        if validate:
            validate_features(frame, self.spec).raise_for_errors()
        return frame[self.spec.model_inputs]

    def base_scores(self, df: pd.DataFrame, validate: bool = True) -> dict[str, np.ndarray]:
        X = self.prepare(df, validate)
        return {name: self.pipelines[name].predict_proba(X)[:, 1] for name in self.weights}

    def predict_proba(self, df: pd.DataFrame, validate: bool = True) -> np.ndarray:
        return self.calibrator.transform(blend(self.base_scores(df, validate), self.weights))

    def risk_tier(self, probability: np.ndarray) -> np.ndarray:
        medium, high = self.risk_cutoffs
        return np.select([probability >= high, probability >= medium], ["high", "medium"], default="low")

    def score(self, df: pd.DataFrame, validate: bool = True) -> pd.DataFrame:
        probability = self.predict_proba(df, validate)
        out = pd.DataFrame(index=df.index)
        for col in ID_COLUMNS:
            if col in df:
                out[col] = df[col].to_numpy()
        out["churn_probability"] = probability
        out["risk_tier"] = self.risk_tier(probability)
        out["target_for_retention"] = probability >= self.threshold
        value = df[VALUE_COLUMN].to_numpy(dtype=float) if VALUE_COLUMN in df else np.full(len(df), np.nan)
        out["expected_revenue_at_risk"] = (probability * value * self.months_of_value).round(2)
        return out.reset_index(drop=True)

    # ------------------------------------------------------- persistence
    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path, compress=3)
        return path

    @staticmethod
    def load(path: Path) -> ChurnModel:
        model = joblib.load(path)
        if not isinstance(model, ChurnModel):
            raise TypeError(f"{path} does not contain a ChurnModel")
        return model

    def describe(self) -> dict[str, Any]:
        return {
            "members": self.weights,
            "threshold": round(self.threshold, 5),
            "risk_cutoffs": [round(c, 5) for c in self.risk_cutoffs],
            "calibration": self.calibrator.method,
            "explainer_model": self.explainer_model,
            "n_features": len(self.spec.model_inputs),
            **self.metadata,
        }
