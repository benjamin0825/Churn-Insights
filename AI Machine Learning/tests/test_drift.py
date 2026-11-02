import numpy as np
import pandas as pd
import pytest

from churn_ml.features import FeatureSpec
from churn_ml.monitoring import DriftProfile, psi
from churn_ml.settings import FeaturesConfig

SPEC = FeatureSpec.from_config(FeaturesConfig())


def _frame(n, seed, shift=0.0, region_p=(0.25, 0.25, 0.25, 0.25)):
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame({col: rng.normal(10, 2, n) for col in SPEC.numeric})
    frame["sessions_mean_4w"] += shift
    for col in SPEC.categorical:
        frame[col] = "a"
    frame["region"] = rng.choice(["north", "south", "east", "west"], n, p=region_p)
    frame[SPEC.text] = np.where(rng.random(n) < 0.3, "router keeps restarting", "")
    return frame


def test_psi_basics():
    assert psi([0.5, 0.5], [0.5, 0.5]) == pytest.approx(0)
    assert psi([0.9, 0.1], [0.1, 0.9]) > 1


def test_identical_distribution_is_stable():
    profile = DriftProfile(SPEC).fit(_frame(5000, 0))
    report = profile.compare(_frame(5000, 1))
    assert report.status == "stable", report.features.head()


def test_shifted_feature_raises_alert():
    profile = DriftProfile(SPEC).fit(_frame(5000, 0))
    report = profile.compare(_frame(5000, 1, shift=3.0))
    top = report.features.iloc[0]
    assert top["feature"] == "sessions_mean_4w" and top["status"] == "alert"
    assert top["ks_pvalue"] < 1e-6


def test_category_mix_and_unseen_values():
    profile = DriftProfile(SPEC).fit(_frame(5000, 0))
    current = _frame(5000, 1, region_p=(0.7, 0.1, 0.1, 0.1))
    current.loc[:500, "plan"] = "brand-new-plan"
    table = profile.compare(current).features.set_index("feature")
    assert table.loc["region", "status"] != "stable"
    assert table.loc["plan", "unseen_share"] > 0.09


def test_segment_drift_finds_localised_shock():
    reference = _frame(8000, 0)
    current = _frame(8000, 1)
    west = current["region"] == "west"
    current.loc[west, "sessions_mean_4w"] -= 3.0  # shock only in one region
    profile = DriftProfile(SPEC, segment_column="region").fit(reference)
    report = profile.compare(current)
    assert report.segments is not None
    top = report.segments.iloc[0]
    assert top["segment"] == "region=west" and top["feature"] == "sessions_mean_4w" and top["status"] == "alert"
    assert report.status == "alert"


def test_prediction_drift_reported():
    rng = np.random.default_rng(0)
    profile = DriftProfile(SPEC).fit(_frame(3000, 0), predictions=rng.beta(1, 10, 3000))
    report = profile.compare(_frame(3000, 1), predictions=rng.beta(3, 6, 3000))
    assert report.prediction["status"] == "alert"
    assert set(report.to_dict()) >= {"status", "features", "prediction", "segments"}
