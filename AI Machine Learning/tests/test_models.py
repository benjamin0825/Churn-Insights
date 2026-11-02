import pickle

import numpy as np
import pytest
from sklearn.base import clone
from sklearn.metrics import brier_score_loss, roc_auc_score

from churn_ml.features import FeatureSpec
from churn_ml.models.calibration import ProbabilityCalibrator, blend, optimise_blend_weights
from churn_ml.models.neural import TabularNNClassifier
from churn_ml.models.preprocessing import Winsorizer, source_feature
from churn_ml.models.zoo import MODEL_SPECS, get_model_spec
from churn_ml.settings import FeaturesConfig


def _toy(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    numeric = rng.normal(size=(n, 4))
    cats = rng.integers(0, 3, size=(n, 2)).astype(float)
    logit = 1.5 * numeric[:, 0] - numeric[:, 1] + 1.2 * (cats[:, 0] == 2) - 1.0
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return np.hstack([numeric, cats]).astype(np.float32), y


def test_neural_net_learns_and_uses_embeddings():
    X, y = _toy()
    model = TabularNNClassifier(n_categorical=2, hidden_sizes=(32, 16), max_epochs=25, random_state=0)
    model.fit(X[:2400], y[:2400])
    p = model.predict_proba(X[2400:])
    assert p.shape == (600, 2) and np.allclose(p.sum(axis=1), 1)
    assert roc_auc_score(y[2400:], p[:, 1]) > 0.75
    assert model.cardinalities_ == [4, 4]  # 3 known codes + the unseen slot
    assert len(model.history_) >= 1


def test_neural_net_handles_unseen_codes_and_pickles():
    X, y = _toy(800)
    model = TabularNNClassifier(n_categorical=2, hidden_sizes=(16,), max_epochs=3).fit(X, y)
    X_new = X[:5].copy()
    X_new[:, -1] = 99  # unseen category code
    expected = model.predict_proba(X_new)
    restored = pickle.loads(pickle.dumps(model))
    np.testing.assert_allclose(restored.predict_proba(X_new), expected, rtol=1e-6)
    assert clone(model).get_params()["hidden_sizes"] == (16,)


@pytest.mark.parametrize("name", sorted(MODEL_SPECS))
def test_every_zoo_model_builds_from_its_search_space(name):
    import optuna

    spec = FeatureSpec.from_config(FeaturesConfig())
    params = get_model_spec(name).space(optuna.create_study().ask())
    estimator = get_model_spec(name).factory(params, spec, 0)
    assert hasattr(estimator, "fit") and hasattr(estimator, "predict_proba")


def test_unknown_model_name():
    with pytest.raises(ValueError):
        get_model_spec("deep_magic")


def test_calibration_improves_brier_on_miscalibrated_scores():
    rng = np.random.default_rng(1)
    true_p = rng.uniform(0, 0.3, 5000)
    y = (rng.random(5000) < true_p).astype(int)
    skewed = np.sqrt(true_p)  # systematically too high
    for method in ("isotonic", "sigmoid"):
        cal = ProbabilityCalibrator(method).fit(skewed[:2500], y[:2500])
        assert brier_score_loss(y[2500:], cal.transform(skewed[2500:])) < brier_score_loss(y[2500:], skewed[2500:])
    assert np.array_equal(ProbabilityCalibrator("none").fit(skewed, y).transform(skewed), skewed)


def test_blend_weights_prefer_the_informative_model():
    rng = np.random.default_rng(2)
    p = rng.uniform(0.01, 0.5, 4000)
    y = (rng.random(4000) < p).astype(int)
    scores = {"good": p, "noise": rng.uniform(0.01, 0.5, 4000)}
    weights = optimise_blend_weights(scores, y)
    assert weights["good"] > 0.8 and abs(sum(weights.values()) - 1) < 1e-6
    assert np.allclose(blend(scores, {"good": 1.0}), p)


def test_winsorizer_clips_to_learned_quantiles():
    X = np.arange(1000, dtype=float).reshape(-1, 1)
    w = Winsorizer(0.01, 0.99).fit(X)
    out = w.transform(np.array([[-1e6], [1e6], [np.nan]]))
    assert out[0, 0] == pytest.approx(w.lower_[0]) and out[1, 0] == pytest.approx(w.upper_[0])
    assert np.isnan(out[2, 0])


def test_source_feature_mapping():
    spec = FeatureSpec.from_config(FeaturesConfig())
    assert source_feature("cat__contract_type_month-to-month", spec) == "contract_type"
    assert source_feature("cat__payment_method_missing", spec) == "payment_method"
    assert source_feature("num__missingindicator_age", spec) == "age"
    assert source_feature("text__truncatedsvd3", spec) == "ticket_text"
