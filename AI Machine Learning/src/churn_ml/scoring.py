"""Batch scoring and drift monitoring against the production model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .explain.shap_explainer import try_explainer
from .logging_utils import get_logger, timed
from .models.churn_model import ChurnModel
from .monitoring.drift import DriftReport
from .registry.model_registry import ModelRegistry, write_json
from .reporting.report import render_drift_report
from .settings import Settings
from .training.dataset import build_scoring_frame, load_raw

log = get_logger(__name__)


def attach_reasons(
    model: ChurnModel, features: pd.DataFrame, scores: pd.DataFrame, top_n: int, only_tiers: tuple[str, ...] = ("high",)
) -> pd.DataFrame:
    """Add a ``top_reasons`` column (SHAP drivers) for customers in the given risk tiers."""
    scores = scores.copy()
    scores["top_reasons"] = ""
    explainer = try_explainer(model)
    if explainer is None:
        return scores
    mask = scores["risk_tier"].isin(only_tiers).to_numpy()
    if mask.any():
        reasons = explainer.reasons(features.loc[mask], top_n)
        scores.loc[mask, "top_reasons"] = [
            "; ".join(f"{r['feature']} ({'+' if r['impact'] > 0 else '-'}{abs(r['impact']):.2f})" for r in items)
            for items in reasons
        ]
    return scores


@dataclass
class ScoringResult:
    week: int
    version: int
    scores: pd.DataFrame
    path: Path


def score_batch(
    settings: Settings, week: int | None = None, version: str | int = "production", explain: bool = True
) -> ScoringResult:
    registry = ModelRegistry(settings.registry_dir)
    resolved = registry.resolve(version)
    model = registry.load(resolved)
    features, week = build_scoring_frame(settings, load_raw(settings), week)
    with timed(log, f"scoring {len(features):,} customers as of week {week} with v{resolved:04d}"):
        scores = model.score(features)
        if explain:
            scores = attach_reasons(model, features, scores, settings.explain.top_reasons)
    scores = scores.sort_values("churn_probability", ascending=False).reset_index(drop=True)
    path = settings.predictions_dir / f"scores_week{week:03d}_v{resolved:04d}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    scores.to_csv(path, index=False)
    summary = scores["risk_tier"].value_counts().to_dict()
    log.info("wrote %s | tiers %s | targeted %s", path.name, summary, int(scores["target_for_retention"].sum()))
    return ScoringResult(week, resolved, scores, path)


@dataclass
class MonitoringResult:
    week: int
    version: int
    report: DriftReport
    json_path: Path
    html_path: Path


def monitor_batch(settings: Settings, week: int | None = None, version: str | int = "production") -> MonitoringResult:
    registry = ModelRegistry(settings.registry_dir)
    resolved = registry.resolve(version)
    model = registry.load(resolved)
    if model.drift_profile is None:
        raise RuntimeError(f"model v{resolved:04d} has no drift profile")
    features, week = build_scoring_frame(settings, load_raw(settings), week)
    mon = settings.monitoring
    report = model.drift_profile.compare(features, model.predict_proba(features), mon.psi_warning, mon.psi_alert)

    out = settings.monitoring_dir
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"drift_week{week:03d}_v{resolved:04d}.json"
    html_path = json_path.with_suffix(".html")
    write_json(json_path, report.to_dict())
    html_path.write_text(render_drift_report(report, week, resolved, mon.psi_warning, mon.psi_alert), encoding="utf-8")
    log.info("drift status %s | drifted: %s", report.status.upper(), report.drifted_features[:8])
    return MonitoringResult(week, resolved, report, json_path, html_path)


def summarise(result: MonitoringResult) -> str:
    top = result.report.features.head(5)[["feature", "psi", "status"]]
    payload = {
        "week": result.week,
        "status": result.report.status,
        "top_features": top.round(4).to_dict(orient="records"),
    }
    if result.report.segments is not None:
        seg = result.report.segments.head(5)[["segment", "feature", "psi", "status"]]
        payload["top_segments"] = seg.round(4).to_dict(orient="records")
    return json.dumps(payload, indent=2)
