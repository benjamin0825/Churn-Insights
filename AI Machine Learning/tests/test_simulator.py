import numpy as np
import pandas as pd
import pytest

from churn_ml.data.simulator import SimulatedData, simulate
from churn_ml.data.validation import validate_raw
from churn_ml.settings import SimulationConfig


@pytest.fixture(scope="module")
def small():
    return simulate(
        SimulationConfig(n_customers=800, new_customers_per_week=5, n_weeks=40, drift={"start_week": 30}), seed=3
    )


def test_deterministic_for_a_seed():
    cfg = SimulationConfig(n_customers=200, new_customers_per_week=2, n_weeks=20)
    a, b = simulate(cfg, seed=11), simulate(cfg, seed=11)
    for name in SimulatedData.TABLES:
        pd.testing.assert_frame_equal(getattr(a, name), getattr(b, name))


def test_raw_tables_pass_integrity_checks(small):
    report = validate_raw(small)
    assert report.ok, report.errors


def test_no_activity_after_churn(small):
    churn = small.customers.set_index("customer_id")["churn_week"].astype("float")
    last_usage = small.usage.groupby("customer_id")["week"].max()
    churned = churn.dropna()
    assert (
        last_usage.reindex(churned.index).dropna() <= churned.loc[last_usage.reindex(churned.index).dropna().index]
    ).all()


def test_competitor_shock_reduces_usage_in_target_region(small):
    usage = small.usage.merge(small.customers[["customer_id", "region"]], on="customer_id")
    usage["period"] = np.where(usage["week"] >= 34, "after", "before")
    usage["west"] = usage["region"] == "west"
    means = usage[usage["week"] >= 24].groupby(["west", "period"])["sessions"].mean()
    west_change = means[(True, "after")] / means[(True, "before")]
    other_change = means[(False, "after")] / means[(False, "before")]
    assert west_change < other_change - 0.1


def test_save_and_load_round_trip(small, tmp_path):
    small.save(tmp_path)
    loaded = SimulatedData.load(tmp_path)
    pd.testing.assert_frame_equal(loaded.tickets, small.tickets)
    with pytest.raises(FileNotFoundError):
        SimulatedData.load(tmp_path / "missing")
