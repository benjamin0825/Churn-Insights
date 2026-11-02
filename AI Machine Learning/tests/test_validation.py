import numpy as np
import pandas as pd
import pytest

from churn_ml.data.validation import DataValidationError, validate_features
from churn_ml.features import FeatureSpec
from churn_ml.settings import FeaturesConfig

SPEC = FeatureSpec.from_config(FeaturesConfig())


def _valid_frame(n=20) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    frame = pd.DataFrame({col: rng.uniform(0, 5, n) for col in SPEC.numeric})
    frame["region"] = "north"
    frame["plan"] = "basic"
    frame["internet_service"] = "dsl"
    frame["contract_type"] = "one-year"
    frame["payment_method"] = "credit-card"
    frame["acquisition_channel"] = "online"
    frame[SPEC.text] = ""
    frame["churned"] = rng.integers(0, 2, n)
    return frame


def test_valid_frame_passes():
    report = validate_features(_valid_frame(), SPEC, require_label=True)
    assert report.ok and not report.warnings


def test_missing_columns_are_errors():
    report = validate_features(_valid_frame().drop(columns=["age", "region"]), SPEC)
    assert not report.ok and "age" in report.errors[0]


def test_negative_counts_and_infinities_are_errors():
    frame = _valid_frame()
    frame.loc[0, "tickets_4w"] = -1
    frame.loc[1, "age"] = np.inf
    report = validate_features(frame, SPEC)
    assert any("tickets_4w" in e for e in report.errors)
    assert any("infinite" in e for e in report.errors)
    with pytest.raises(DataValidationError):
        report.raise_for_errors()


def test_unseen_category_is_only_a_warning():
    frame = _valid_frame()
    frame.loc[0, "region"] = "atlantis"
    report = validate_features(frame, SPEC)
    assert report.ok and "atlantis" in report.warnings[0]


def test_bad_labels_detected():
    frame = _valid_frame()
    frame.loc[0, "churned"] = 3
    assert not validate_features(frame, SPEC, require_label=True).ok
