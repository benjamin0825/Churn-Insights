"""End-to-end training: features -> tuning -> ensemble -> calibration -> policy -> registry."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline

from .. import __version__
from ..data.simulator import SimulatedData
from ..data.validation import validate_features, validate_raw
from ..explain.shap_explainer import try_explainer
from ..features.spec import LABEL, VALUE_COLUMN
from ..logging_utils import get_logger, timed
from ..models.calibration import ProbabilityCalibrator, blend, optimise_blend_weights
from ..models.churn_model import ChurnModel
from ..models.preprocessing import build_preprocessor
from ..models.zoo import get_model_spec
from ..monitoring.drift import DriftProfile
from ..registry.model_registry import ModelRegistry
from ..reporting import charts
from ..reporting.report import render_training_report
from ..settings import Settings
from .dataset import build_training_frame, feature_fingerprint, load_raw
from .metrics import full_report, profit_curve, ranking_metrics, score_for_tuning
from .splits import temporal_split
from .tracking import Tracker
from .tuning import tune

log = get_logger(__name__)
SPLITS = ("train", "validation", "test")


@dataclass
class TrainingOutcome:
    version: int
    promoted: bool
    decision: dict
    metrics: dict
    leaderboard: pd.DataFrame
    report_path: Path
    model: ChurnModel


def _members(
    names: list[str], val_scores: dict[str, np.ndarray], y_val: np.ndarray, settings: Settings
) -> dict[str, float]:
    metric = settings.tuning.metric
    ranked = sorted(names, key=lambda n: score_for_tuning(metric, y_val, val_scores[n]), reverse=True)
    if not settings.ensemble.enabled:
        return {ranked[0]: 1.0}
    top = ranked[: settings.ensemble.top_k]
    weights = optimise_blend_weights({n: val_scores[n] for n in top}, y_val)
    kept = {n: w for n, w in weights.items() if w >= 0.02} or {ranked[0]: 1.0}
    total = sum(kept.values())
    return {n: w / total for n, w in kept.items()}


def _explainer_member(weights: dict[str, float], names: list[str], val_scores, y_val) -> str | None:
    trees = [n for n in names if get_model_spec(n).is_tree]
    in_blend = [n for n in trees if n in weights]
    if in_blend:
        return max(in_blend, key=weights.get)
    if trees:
        return max(trees, key=lambda n: roc_auc_score(y_val, val_scores[n]))
    return None


def train(settings: Settings, data: SimulatedData | None = None) -> TrainingOutcome:
    seed = settings.project.seed
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tracker = Tracker(settings)

    data = data if data is not None else load_raw(settings, simulate_if_missing=True)
    raw_report = validate_raw(data).raise_for_errors()
    frame, spec = build_training_frame(settings, data)
    validate_features(frame, spec, require_label=True).raise_for_errors()

    plan, *parts = temporal_split(frame, settings)
    dfs = dict(zip(SPLITS, parts))
    y = {k: dfs[k][LABEL].to_numpy(dtype=int) for k in SPLITS}
    inputs = spec.model_inputs
    log.info("split %s | rows %s", plan.describe(), {k: len(v) for k, v in dfs.items()})

    with tracker.run(f"train-{run_id}"):
        tracker.log_params({"config": settings.model_dump(mode="json")})
        tracker.set_tags({"run_id": run_id, "package_version": __version__})

        # 1. Fit each required preprocessing variant once.
        enabled = list(settings.models.enabled)
        encodings = sorted({get_model_spec(n).encoding for n in enabled})
        preprocessors, matrices = {}, {}
        for enc in encodings:
            with timed(log, f"fitting {enc} preprocessor"):
                pre = build_preprocessor(spec, settings.features, enc, seed).fit(dfs["train"][inputs], y["train"])
                preprocessors[enc] = pre
                matrices[enc] = {k: pre.transform(dfs[k][inputs]).astype(np.float32) for k in SPLITS}
        log.info("design matrix width: %s", {e: m["train"].shape[1] for e, m in matrices.items()})

        # 2. Tune and fit every candidate.
        storage = settings.resolve_uri(settings.tuning.storage)
        if storage:
            settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
        pipelines, val_scores, test_scores, best_params, rows = {}, {}, {}, {}, []
        for name in enabled:
            model_spec = get_model_spec(name)
            M = matrices[model_spec.encoding]
            result = tune(
                name,
                M["train"],
                y["train"],
                M["validation"],
                y["validation"],
                spec,
                settings.tuning,
                seed,
                storage,
                study_prefix=run_id,
            )
            start = time.perf_counter()
            estimator = model_spec.factory(result.best_params, spec, seed).fit(M["train"], y["train"])
            fit_seconds = time.perf_counter() - start
            pipelines[name] = Pipeline([("preprocess", preprocessors[model_spec.encoding]), ("model", estimator)])
            val_scores[name] = estimator.predict_proba(M["validation"])[:, 1]
            test_scores[name] = estimator.predict_proba(M["test"])[:, 1]
            best_params[name] = result.best_params
            val_rank, test_rank = (
                ranking_metrics(y["validation"], val_scores[name]),
                ranking_metrics(y["test"], test_scores[name]),
            )
            rows.append(
                {
                    "model": name,
                    "val_score": score_for_tuning(settings.tuning.metric, y["validation"], val_scores[name]),
                    "val_roc_auc": val_rank["roc_auc"],
                    "test_roc_auc": test_rank["roc_auc"],
                    "test_average_precision": test_rank["average_precision"],
                    "trials": result.n_trials,
                    "tune_seconds": result.seconds,
                    "fit_seconds": fit_seconds,
                }
            )
            log.info(
                "fitted %-20s val AUC %.4f | test AUC %.4f (%.1fs)",
                name,
                val_rank["roc_auc"],
                test_rank["roc_auc"],
                fit_seconds,
            )
            tracker.log_metrics({"val_roc_auc": val_rank["roc_auc"], "test_roc_auc": test_rank["roc_auc"]}, prefix=name)

        # 3. Blend, calibrate and choose the business threshold on validation.
        weights = _members(enabled, val_scores, y["validation"], settings)
        raw_val, raw_test = blend(val_scores, weights), blend(test_scores, weights)
        calibrator = ProbabilityCalibrator(settings.calibration.method).fit(raw_val, y["validation"])
        p_val, p_test = calibrator.transform(raw_val), calibrator.transform(raw_test)
        value = {k: dfs[k][VALUE_COLUMN].to_numpy(dtype=float) for k in SPLITS}
        curve_val = profit_curve(y["validation"], p_val, value["validation"], settings.business)
        threshold = curve_val.best_threshold
        risk_cutoffs = (float(np.quantile(p_val, 0.70)), float(np.quantile(p_val, 0.90)))
        log.info("blend weights %s | threshold %.4f", {k: round(v, 3) for k, v in weights.items()}, threshold)

        val_report = full_report(y["validation"], p_val, value["validation"], threshold, settings.business)
        test_report = full_report(y["test"], p_test, value["test"], threshold, settings.business)
        rows.append(
            {
                "model": "final model",
                "val_score": score_for_tuning(settings.tuning.metric, y["validation"], p_val),
                "val_roc_auc": val_report["roc_auc"],
                "test_roc_auc": test_report["roc_auc"],
                "test_average_precision": test_report["average_precision"],
                "trials": None,
                "tune_seconds": None,
                "fit_seconds": None,
            }
        )
        for row in rows:
            row["weight"] = weights.get(row["model"]) if row["model"] != "final model" else None
        leaderboard = pd.DataFrame(rows)

        # 4. Assemble the bundle (plus one tree member for SHAP if none is blended).
        explainer_name = _explainer_member(weights, enabled, val_scores, y["validation"])
        keep = set(weights) | ({explainer_name} if explainer_name else set())
        model = ChurnModel(
            pipelines={n: pipelines[n] for n in keep},
            weights=weights,
            calibrator=calibrator,
            threshold=threshold,
            spec=spec,
            risk_cutoffs=risk_cutoffs,
            months_of_value=settings.business.months_of_value,
            explainer_model=explainer_name,
            metadata={
                "run_id": run_id,
                "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "split": plan.describe(),
                "package_version": __version__,
                "feature_fingerprint": feature_fingerprint(settings),
            },
        )
        reference = dfs["train"].sample(min(settings.monitoring.reference_sample, len(dfs["train"])), random_state=seed)
        model.drift_profile = DriftProfile(spec, seed=seed, segment_column=settings.monitoring.segment_column).fit(
            reference, model.predict_proba(reference, validate=False)
        )

        importance = pd.Series(dtype=float)
        explainer = try_explainer(model)
        if explainer is not None:
            sample = dfs["validation"].sample(
                min(settings.explain.background_rows, len(dfs["validation"])), random_state=seed
            )
            with timed(log, "computing SHAP importance"):
                importance = explainer.global_importance(sample)

        metrics = {
            "run_id": run_id,
            "split": plan.describe(),
            "weights": weights,
            "threshold": threshold,
            "validation": val_report,
            "test": test_report,
            "leaderboard": rows,
            "best_params": best_params,
            "global_importance": importance.round(5).to_dict(),
            "raw_data": raw_report.stats,
            "rows": {k: len(v) for k, v in dfs.items()},
        }

        # 5. Champion/challenger, registration, report.
        registry = ModelRegistry(settings.registry_dir)
        decision = registry.champion_challenger(model, dfs["test"], y["test"], settings.registry.tolerance)
        metrics["promotion"] = decision
        version = registry.register(model, metrics, tags={"run_id": run_id})

        report_html = _report(
            version,
            run_id,
            model,
            metrics,
            plan.describe(),
            dfs,
            y,
            frame,
            val_scores,
            test_scores,
            raw_test,
            p_val,
            p_test,
            value,
            curve_val,
            importance,
            settings,
            decision,
        )
        report_path = registry.version_dir(version) / "report.html"
        report_path.write_text(report_html, encoding="utf-8")

        promoted = bool(settings.registry.auto_promote and decision["promote"])
        if promoted:
            registry.promote(version, reason=decision["reason"])
        else:
            log.warning("v%04d registered but not promoted: %s", version, decision["reason"])

        tracker.log_metrics(test_report, prefix="test")
        tracker.log_metrics(val_report, prefix="validation")
        tracker.set_tags({"registry_version": version, "promoted": promoted})
        tracker.log_artifact(report_path)
        tracker.log_artifact(registry.version_dir(version) / "metrics.json")

    log.info(
        "v%04d test ROC AUC %.4f | AP %.4f | profit $%.0f | report %s",
        version,
        test_report["roc_auc"],
        test_report["average_precision"],
        test_report["campaign_profit"],
        report_path,
    )
    return TrainingOutcome(version, promoted, decision, metrics, leaderboard, report_path, model)


def _report(
    version,
    run_id,
    model,
    metrics,
    split,
    dfs,
    y,
    frame,
    val_scores,
    test_scores,
    raw_test,
    p_val,
    p_test,
    value,
    curve_val,
    importance,
    settings: Settings,
    decision,
) -> str:
    curve_test = profit_curve(y["test"], p_test, value["test"], settings.business)
    share_val = float(np.mean(p_val >= model.threshold))
    share_test = float(np.mean(p_test >= model.threshold))
    scores = {**test_scores, "final model": p_test}
    chart_uris = {
        "roc": charts.roc_chart(y["test"], scores),
        "pr": charts.pr_chart(y["test"], scores),
        "calibration": charts.calibration_chart(y["test"], raw_test, p_test),
        "gains": charts.gains_chart(y["test"], p_test),
        "profit_val": charts.profit_chart(
            curve_val.targeted_share,
            curve_val.profit,
            share_val,
            metrics["validation"]["campaign_profit"],
            "Profit curve, validation (threshold chosen here)",
        ),
        "profit_test": charts.profit_chart(
            curve_test.targeted_share,
            curve_test.profit,
            share_test,
            metrics["test"]["campaign_profit"],
            "Profit curve, test (threshold applied)",
        ),
        "over_time": charts.churn_over_time_chart(frame.groupby("snapshot_week")[LABEL].mean(), split),
        "importance": charts.importance_chart(importance) if len(importance) else None,
    }
    return render_training_report(
        {
            "version": version,
            "run_id": run_id,
            "trained_at": model.metadata["trained_at"],
            "split": split,
            "rows": metrics["rows"],
            "rates": {k: float(np.mean(y[k])) for k in SPLITS},
            "test": metrics["test"],
            "leaderboard": sorted(
                metrics["leaderboard"], key=lambda r: (r["model"] != "final model", -r["test_roc_auc"])
            ),
            "tuning_metric": settings.tuning.metric.replace("_", " "),
            "charts": chart_uris,
            "business": settings.business,
            "importance": list(importance.head(15).round(4).items()),
            "best_params": metrics["best_params"],
            "promotion": decision,
        }
    )
