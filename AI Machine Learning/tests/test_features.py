import numpy as np
import pandas as pd
import pytest

from churn_ml.data.simulator import SimulatedData, simulate
from churn_ml.data.validation import validate_features
from churn_ml.features import LABEL, FeatureBuilder
from churn_ml.settings import FeaturesConfig, SimulationConfig

CFG = FeaturesConfig(tfidf_max_features=200, svd_components=4)


@pytest.fixture(scope="module")
def data():
    return simulate(SimulationConfig(n_customers=700, new_customers_per_week=4, n_weeks=48), seed=5)


def _truncate(data: SimulatedData, week: int) -> SimulatedData:
    """Drop every event at or after ``week`` -- what the world looked like at that time."""
    customers = data.customers.copy()
    customers.loc[customers["churn_week"] >= week, "churn_week"] = pd.NA
    return SimulatedData(
        customers=customers[customers["signup_week"] < week].reset_index(drop=True),
        usage=data.usage[data.usage["week"] < week],
        billing=data.billing[data.billing["week"] < week],
        tickets=data.tickets[data.tickets["week"] < week],
    )


def test_features_are_point_in_time_correct(data):
    """Future events must not change a snapshot's features (no leakage)."""
    week = 30
    full = FeatureBuilder(data, CFG, horizon_weeks=8).build_snapshot(week)
    past = FeatureBuilder(_truncate(data, week), CFG, horizon_weeks=8).build_snapshot(week)
    cols = [c for c in full.columns if c != LABEL]
    pd.testing.assert_frame_equal(full[cols], past[cols], check_dtype=False)


def test_population_and_labels(data):
    week, horizon = 24, 8
    frame = FeatureBuilder(data, CFG, horizon).build_snapshot(week)
    customers = data.customers.set_index("customer_id")
    rows = customers.loc[frame["customer_id"]]
    assert (rows["signup_week"] < week).all()
    assert ((rows["churn_week"].isna()) | (rows["churn_week"] >= week)).all()
    expected = ((rows["churn_week"] >= week) & (rows["churn_week"] < week + horizon)).fillna(False).astype(int)
    np.testing.assert_array_equal(frame[LABEL].to_numpy(), expected.to_numpy())


def test_scoring_snapshot_has_no_label(data):
    builder = FeatureBuilder(data, CFG, horizon_weeks=8)
    frame = builder.build_snapshot(builder.n_weeks)
    assert frame[LABEL].isna().all()
    assert len(frame) > 0


def test_feature_frame_passes_validation(data):
    builder = FeatureBuilder(data, CFG, horizon_weeks=8)
    frame = builder.build_many([16, 20, 24])
    report = validate_features(frame, builder.spec, require_label=True)
    assert report.ok, report.errors
    assert set(frame["snapshot_week"]) == {16, 20, 24}
    assert frame[builder.spec.text].map(type).eq(str).all()


def test_windows_drive_feature_names():
    from churn_ml.features import FeatureSpec

    spec = FeatureSpec.from_config(FeaturesConfig(windows_weeks=[2, 8]))
    assert "sessions_mean_2w" in spec.numeric and "minutes_std_8w" in spec.numeric
    assert spec.model_inputs[-1] == spec.text
