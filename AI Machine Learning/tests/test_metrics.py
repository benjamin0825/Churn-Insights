import numpy as np
import pytest

from churn_ml.settings import BusinessConfig
from churn_ml.training.metrics import (
    business_metrics,
    expected_calibration_error,
    full_report,
    profit_curve,
    top_fraction_stats,
)
from churn_ml.training.splits import plan_split

BUSINESS = BusinessConfig(offer_cost=10, retention_success_rate=0.5, months_of_value=10)


def test_profit_curve_by_hand():
    y = np.array([1, 0, 1, 0])
    p = np.array([0.9, 0.8, 0.3, 0.1])
    value = np.array([10.0, 10.0, 10.0, 10.0])  # a saved churner is worth 0.5 * 10 * 10 = 50
    curve = profit_curve(y, p, value, BUSINESS)
    np.testing.assert_allclose(curve.profit, [0, 40, 30, 70, 60])
    assert curve.best_index == 3 and curve.best_threshold == pytest.approx(0.3)
    bm = business_metrics(y, p, value, curve.best_threshold, BUSINESS)
    assert bm["campaign_profit"] == pytest.approx(70) and bm["customers_targeted"] == 3


def test_top_fraction_lift():
    y = np.array([1] * 10 + [0] * 90)
    p = np.linspace(1, 0, 100)
    lift, recall = top_fraction_stats(y, p, 0.1)
    assert lift == pytest.approx(10) and recall == pytest.approx(1.0)


def test_ece_zero_for_perfectly_calibrated_bins():
    p = np.repeat([0.1, 0.5], 1000)
    y = np.concatenate([np.r_[np.ones(100), np.zeros(900)], np.r_[np.ones(500), np.zeros(500)]])
    assert expected_calibration_error(y, p, bins=2) == pytest.approx(0, abs=1e-9)


def test_full_report_keys():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 500)
    report = full_report(y, rng.random(500), rng.uniform(20, 90, 500), 0.5, BUSINESS)
    for key in ("roc_auc", "average_precision", "brier", "ece", "lift_at_10pct", "campaign_profit", "recall"):
        assert key in report


def test_split_embargo():
    weeks = list(range(20, 100, 4))
    plan = plan_split(weeks, horizon=8, n_validation=2, n_test=2)
    assert plan.test_weeks == [92, 96]
    assert max(plan.validation_weeks) + 8 <= min(plan.test_weeks)
    assert max(plan.train_weeks) + 8 <= min(plan.validation_weeks)
    assert set(plan.embargoed_weeks) == {88, 76}
    with pytest.raises(ValueError):
        plan_split([20, 24, 28], horizon=8, n_validation=2, n_test=2)
