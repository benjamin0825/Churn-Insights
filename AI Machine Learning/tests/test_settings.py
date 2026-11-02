import pytest
from pydantic import ValidationError

from churn_ml.settings import PROJECT_ROOT, load_settings


def test_default_profile_loads():
    s = load_settings()
    assert s.simulation.n_weeks == 104
    assert s.artifacts_dir == PROJECT_ROOT / "artifacts"


def test_profile_merges_over_defaults():
    s = load_settings("fast")
    assert s.simulation.n_customers == 2500
    assert s.business.offer_cost == 15.0  # untouched default survives the merge


def test_dotted_overrides_are_yaml_parsed():
    s = load_settings(
        overrides=["tuning.n_trials.lightgbm=7", "models.enabled=[lightgbm, xgboost]", "tracking.enabled=false"]
    )
    assert s.tuning.n_trials["lightgbm"] == 7
    assert s.models.enabled == ["lightgbm", "xgboost"]
    assert s.tracking.enabled is False


def test_invalid_values_are_rejected():
    with pytest.raises(ValidationError):
        load_settings(overrides=["models.enabled=[not_a_model]"])
    with pytest.raises(ValueError):
        load_settings(overrides=["no-equals-sign"])


def test_labelled_snapshots_respect_horizon():
    s = load_settings()
    weeks = s.labelled_snapshots()
    assert weeks[0] == s.labeling.first_snapshot_week
    assert weeks[-1] + s.labeling.horizon_weeks <= s.simulation.n_weeks
    assert all(b - a == s.labeling.snapshot_every_weeks for a, b in zip(weeks, weeks[1:]))


def test_uri_placeholder_expands():
    s = load_settings()
    assert s.resolve_uri("sqlite:///{artifacts}/x.db").endswith("/artifacts/x.db")
    assert s.resolve_uri(None) is None
