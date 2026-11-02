import pytest

from churn_ml.settings import load_settings
from churn_ml.training.dataset import simulate_and_save


@pytest.fixture(scope="session")
def settings(tmp_path_factory):
    root = tmp_path_factory.mktemp("artifacts")
    return load_settings(
        "fast",
        [
            f"paths.artifacts={root.as_posix()}",
            "models.enabled=[logistic_regression, lightgbm, tabular_nn]",
            "tuning.n_trials.lightgbm=2",
            "tuning.n_trials.tabular_nn=1",
        ],
    )


@pytest.fixture(scope="session")
def raw(settings):
    return simulate_and_save(settings)


@pytest.fixture(scope="session")
def trained(settings, raw):
    from churn_ml.training.trainer import train

    return train(settings, raw)
