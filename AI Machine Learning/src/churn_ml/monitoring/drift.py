"""Data and prediction drift: PSI per feature plus KS tests for numeric columns.

A ``DriftProfile`` is fitted on the training data and stored inside the model
bundle, so production batches can be checked without access to training data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from .. import kernels
from ..features.spec import FeatureSpec

_EPS = 1e-4
MISSING, OTHER = "__missing__", "__other__"
PREDICTION = "__prediction__"
TEXT_LENGTH = "ticket_text_length"


def psi(expected: np.ndarray, actual: np.ndarray) -> float:
    e = np.clip(np.asarray(expected, dtype=float), _EPS, None)
    a = np.clip(np.asarray(actual, dtype=float), _EPS, None)
    e, a = e / e.sum(), a / a.sum()
    return float(np.sum((a - e) * np.log(a / e)))


@dataclass
class FeatureProfile:
    name: str
    kind: str  # "numeric" | "categorical"
    edges: np.ndarray | None = None
    categories: list[str] | None = None
    frequencies: np.ndarray = field(default_factory=lambda: np.empty(0))
    sample: np.ndarray | None = None  # reference sample for the KS test

    @classmethod
    def numeric(cls, name: str, values: np.ndarray, bins: int, sample_size: int, rng) -> FeatureProfile:
        finite = values[~np.isnan(values)]
        edges = np.unique(np.quantile(finite, np.linspace(0, 1, bins + 1)[1:-1])) if len(finite) else np.array([])
        profile = cls(name, "numeric", edges=edges)
        profile.frequencies = profile._numeric_hist(values)
        take = min(sample_size, len(finite))
        profile.sample = rng.choice(finite, take, replace=False) if take else finite
        return profile

    @classmethod
    def categorical(cls, name: str, values: pd.Series) -> FeatureProfile:
        counts = values.fillna(MISSING).astype(str).value_counts(normalize=True)
        categories = [c for c in counts.index if c != MISSING]
        profile = cls(name, "categorical", categories=categories)
        profile.frequencies = profile._categorical_hist(values)
        return profile

    def _numeric_hist(self, values: np.ndarray) -> np.ndarray:
        return kernels.binned_frequencies(values, self.edges)  # quantile bins + a NaN bin

    def _categorical_hist(self, values: pd.Series) -> np.ndarray:
        labels = values.fillna(MISSING).astype(str)
        known = labels.isin(self.categories)
        counts = [float((labels == c).sum()) for c in self.categories]
        counts += [float((~known & (labels != MISSING)).sum()), float((labels == MISSING).sum())]
        return np.asarray(counts) / max(len(labels), 1)

    def compare(self, values) -> dict:
        if self.kind == "numeric":
            arr = np.asarray(values, dtype=float)
            current = self._numeric_hist(arr)
            finite = arr[~np.isnan(arr)]
            pvalue = float(ks_2samp(self.sample, finite).pvalue) if len(finite) and len(self.sample) else None
            return {
                "psi": psi(self.frequencies, current),
                "ks_pvalue": pvalue,
                "reference_mean": float(np.nanmean(self.sample)) if len(self.sample) else None,
                "current_mean": float(np.nanmean(arr)) if len(finite) else None,
            }
        current = self._categorical_hist(pd.Series(values))
        return {
            "psi": psi(self.frequencies, current),
            "ks_pvalue": None,
            "unseen_share": float(current[-2]),
            "reference_mean": None,
            "current_mean": None,
        }


@dataclass
class DriftReport:
    features: pd.DataFrame
    prediction: dict | None
    status: str
    n_reference: int
    n_current: int
    segments: pd.DataFrame | None = None  # per-segment PSI rows (segment, feature, psi, status)

    def to_dict(self, max_segment_rows: int = 50) -> dict:
        rows = self.features.replace({np.nan: None}).to_dict(orient="records")
        segments = None
        if self.segments is not None:
            top = self.segments.head(max_segment_rows)[
                ["segment", "feature", "psi", "status", "reference_mean", "current_mean"]
            ]
            segments = top.replace({np.nan: None}).to_dict(orient="records")
        return {
            "status": self.status,
            "n_reference": self.n_reference,
            "n_current": self.n_current,
            "prediction": self.prediction,
            "features": rows,
            "segments": segments,
        }

    @property
    def drifted_features(self) -> list[str]:
        return self.features.loc[self.features["status"] != "stable", "feature"].tolist()


class DriftProfile:
    MIN_SEGMENT_ROWS = 200

    def __init__(
        self,
        spec: FeatureSpec,
        bins: int = 10,
        sample_size: int = 2000,
        seed: int = 42,
        segment_column: str | None = None,
    ):
        self.spec, self.bins, self.sample_size, self.seed = spec, bins, sample_size, seed
        self.segment_column = segment_column
        self.profiles: dict[str, FeatureProfile] = {}
        self.segments: dict[str, DriftProfile] = {}
        self.n_reference = 0

    @staticmethod
    def _text_length(df: pd.DataFrame, spec: FeatureSpec) -> np.ndarray:
        return df[spec.text].fillna("").astype(str).str.len().to_numpy(dtype=float)

    def fit(self, df: pd.DataFrame, predictions: np.ndarray | None = None) -> DriftProfile:
        rng = np.random.default_rng(self.seed)
        for col in self.spec.numeric:
            self.profiles[col] = FeatureProfile.numeric(
                col, df[col].to_numpy(dtype=float), self.bins, self.sample_size, rng
            )
        for col in self.spec.categorical:
            self.profiles[col] = FeatureProfile.categorical(col, df[col])
        self.profiles[TEXT_LENGTH] = FeatureProfile.numeric(
            TEXT_LENGTH, self._text_length(df, self.spec), self.bins, self.sample_size, rng
        )
        if predictions is not None:
            self.profiles[PREDICTION] = FeatureProfile.numeric(
                PREDICTION, np.asarray(predictions, dtype=float), self.bins, self.sample_size, rng
            )
        self.n_reference = len(df)

        # Localised shocks (one region, one plan...) vanish in global PSI, so profile each segment too.
        if self.segment_column:
            preds = None if predictions is None else np.asarray(predictions, dtype=float)
            for value in df[self.segment_column].dropna().unique():
                mask = (df[self.segment_column] == value).to_numpy()
                if mask.sum() >= self.MIN_SEGMENT_ROWS:
                    child = DriftProfile(self.spec, self.bins, min(self.sample_size, 1000), self.seed)
                    self.segments[str(value)] = child.fit(df.loc[mask], None if preds is None else preds[mask])
        return self

    def compare(
        self, df: pd.DataFrame, predictions: np.ndarray | None = None, warning: float = 0.10, alert: float = 0.25
    ) -> DriftReport:
        def status(value: float) -> str:
            return "alert" if value >= alert else "warning" if value >= warning else "stable"

        rows = []
        for name, profile in self.profiles.items():
            if name == PREDICTION:
                continue
            values = self._text_length(df, self.spec) if name == TEXT_LENGTH else df[name]
            result = profile.compare(values)
            rows.append({"feature": name, "kind": profile.kind, **result, "status": status(result["psi"])})
        table = (
            pd.DataFrame(rows).sort_values("psi", ascending=False).reset_index(drop=True)
            if rows
            else pd.DataFrame(columns=["feature", "kind", "psi", "ks_pvalue", "status"])
        )

        prediction = None
        if predictions is not None and PREDICTION in self.profiles:
            prediction = self.profiles[PREDICTION].compare(np.asarray(predictions, dtype=float))
            prediction["status"] = status(prediction["psi"])

        segments = self._compare_segments(df, predictions, warning, alert)
        levels = list(table["status"]) + ([prediction["status"]] if prediction else [])
        if segments is not None:
            levels += list(segments["status"])
        overall = "alert" if "alert" in levels else "warning" if "warning" in levels else "stable"
        return DriftReport(table, prediction, overall, self.n_reference, len(df), segments)

    def _compare_segments(self, df, predictions, warning, alert) -> pd.DataFrame | None:
        if not self.segments or self.segment_column not in df:
            return None
        preds = None if predictions is None else np.asarray(predictions, dtype=float)
        frames = []
        for value, child in self.segments.items():
            mask = (df[self.segment_column].astype(str) == value).to_numpy()
            if mask.sum() < 50:
                continue
            report = child.compare(df.loc[mask], None if preds is None else preds[mask], warning, alert)
            part = report.features[report.features["kind"] == "numeric"].copy()
            if report.prediction:
                part = pd.concat(
                    [part, pd.DataFrame([{"feature": PREDICTION, "kind": "numeric", **report.prediction}])]
                )
            part.insert(0, "segment", f"{self.segment_column}={value}")
            frames.append(part)
        if not frames:
            return None
        return pd.concat(frames, ignore_index=True).sort_values("psi", ascending=False).reset_index(drop=True)
