"""End-to-end: train real models on the fast profile, then score, explain, monitor and manage versions."""

import copy

import numpy as np
import pytest

from churn_ml.explain import ShapExplainer
from churn_ml.features import LABEL
from churn_ml.models import ChurnModel
from churn_ml.registry import ModelRegistry, RegistryError
from churn_ml.scoring import monitor_batch, score_batch
from churn_ml.training.dataset import build_scoring_frame

pytestmark = pytest.mark.slow


def test_training_produces_a_useful_registered_model(trained, settings):
    test = trained.metrics["test"]
    assert test["roc_auc"] > 0.68
    assert test["lift_at_10pct"] > 1.8
    assert test["ece"] < 0.05
    assert trained.version == 1 and trained.promoted
    assert set(trained.model.weights) <= set(settings.models.enabled)
    assert abs(sum(trained.model.weights.values()) - 1) < 1e-6
    assert trained.report_path.exists() and "ROC curve" in trained.report_path.read_text(encoding="utf-8")
    board = trained.leaderboard.set_index("model")
    assert {"logistic_regression", "lightgbm", "tabular_nn", "final model"} <= set(board.index)


def test_model_round_trips_through_the_registry(trained, settings, raw):
    model = ModelRegistry(settings.registry_dir).load("production")
    frame, _ = build_scoring_frame(settings, raw)
    np.testing.assert_allclose(model.predict_proba(frame), trained.model.predict_proba(frame))
    scores = model.score(frame)
    assert scores["churn_probability"].between(0, 1).all()
    assert set(scores["risk_tier"]) <= {"low", "medium", "high"}
    assert (scores["target_for_retention"] == (scores["churn_probability"] >= model.threshold)).all()


def test_shap_reasons_are_readable(trained, raw, settings):
    explainer = ShapExplainer(trained.model)
    frame, _ = build_scoring_frame(settings, raw)
    reasons = explainer.reasons(frame.head(3), top_n=4)
    assert len(reasons) == 3 and all(len(r) == 4 for r in reasons)
    assert all(item["feature"] in trained.model.spec.model_inputs for r in reasons for item in r)
    importance = trained.metrics["global_importance"]
    assert importance and max(importance.values()) > 0


def test_batch_scoring_writes_ranked_csv(trained, settings):
    result = score_batch(settings)
    assert result.path.exists()
    scores = result.scores
    assert scores["churn_probability"].is_monotonic_decreasing
    assert scores.loc[scores["risk_tier"] == "high", "top_reasons"].str.len().gt(0).all()


def test_monitoring_detects_the_competitor_shock(trained, settings):
    result = monitor_batch(settings)
    assert result.html_path.exists() and result.json_path.exists()
    segments = result.report.segments
    west = segments[segments["segment"] == "region=west"]
    assert (west["status"] == "alert").any()
    assert segments.iloc[0]["segment"] == "region=west"


def test_registry_promotion_and_rollback(trained, settings, tmp_path):
    registry = ModelRegistry(tmp_path / "registry")
    with pytest.raises(RegistryError):
        registry.load("production")
    first = registry.register(copy.deepcopy(trained.model), trained.metrics)
    second = registry.register(copy.deepcopy(trained.model), trained.metrics)
    registry.promote(first)
    registry.promote(second)
    assert registry.production_version() == second
    assert registry.rollback() == first
    table = registry.list().set_index("version")
    assert table.loc[first, "stage"] == "production" and table.loc[second, "stage"] == "archived"
    assert isinstance(registry.load(first), ChurnModel)


def test_champion_challenger_rejects_a_worse_model(trained, settings, raw):
    registry = ModelRegistry(settings.registry_dir)
    frame, _ = build_scoring_frame(settings, raw, week=settings.last_labelled_snapshot())
    y = frame[LABEL].to_numpy(dtype=int)
    bad = copy.deepcopy(trained.model)
    bad.calibrator.transform = lambda s: np.random.default_rng(0).random(len(s))  # random scores
    decision = registry.champion_challenger(bad, frame, y, tolerance=0.005)
    assert decision["promote"] is False and "champion retained" in decision["reason"]
