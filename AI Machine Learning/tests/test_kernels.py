"""Every kernel backend must match the NumPy implementation and pandas exactly.

Compiled backends (``ext`` = churn_ml._kernels_ext, ``native`` = bundled engine) are tested
when they import on this platform.
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from churn_ml import _kernels_py, kernels
from churn_ml.data.simulator import simulate
from churn_ml.features import FeatureBuilder
from churn_ml.settings import FeaturesConfig, SimulationConfig

COMPILED = {n: m for n, m in kernels.available_backends().items() if n != "numpy"}
BACKENDS = [pytest.param(m, id=n) for n, m in COMPILED.items()] + [pytest.param(_kernels_py, id="numpy")]
COMPILED_PARAMS = [pytest.param(m, id=n) for n, m in COMPILED.items()] or [
    pytest.param(None, marks=pytest.mark.skip(reason="no compiled backend available"))
]


@pytest.fixture(scope="module")
def events():
    rng = np.random.default_rng(0)
    n, groups = 20_000, 500
    codes = rng.integers(-1, groups, n).astype(np.int32)  # -1 = row to ignore
    values = rng.normal(size=(n, 3))
    values[rng.random(n) < 0.01, 1] = 7.5  # repeated values
    return codes, values, groups


def _is_compiled(module) -> bool:
    """True when ``module`` is a compiled extension or a package of compiled submodules."""
    path = getattr(module, "__file__", "")
    if path.endswith((".pyd", ".so")):
        return True
    pkg_dir = Path(path).parent  # the _native package: at least one compiled submodule
    return bool(list(pkg_dir.glob("*.pyd")) or list(pkg_dir.glob("*.so")))


def test_dispatch_prefers_compiled_backends():
    forced = os.environ.get("CHURN_ML_KERNELS", "auto")
    expected = forced if forced != "auto" else next(iter(kernels.available_backends()))
    assert kernels.BACKEND == expected
    for module in COMPILED.values():
        assert _is_compiled(module)
    with pytest.raises(ValueError):
        kernels.load_backend("gpu")


@pytest.mark.parametrize("backend", BACKENDS)
def test_group_stats_matches_pandas(backend, events):
    codes, values, groups = events
    sums, sumsq, counts = kernels.group_stats(codes, values, groups, backend=backend)
    frame = pd.DataFrame(values).assign(g=codes).query("g >= 0")
    expected = frame.groupby("g").sum().reindex(range(groups), fill_value=0)
    np.testing.assert_allclose(sums, expected.to_numpy(), rtol=1e-10, atol=1e-10)
    np.testing.assert_array_equal(counts, frame.groupby("g").size().reindex(range(groups), fill_value=0))
    np.testing.assert_allclose(
        sumsq[:, 0], (frame[0] ** 2).groupby(frame["g"]).sum().reindex(range(groups), fill_value=0)
    )


@pytest.mark.parametrize("backend", BACKENDS)
def test_mean_std_match_pandas(backend, events):
    codes, values, groups = events
    mean, std, _ = kernels.group_mean_std(codes, values, groups, backend=backend)
    frame = pd.DataFrame(values).assign(g=codes).query("g >= 0").groupby("g")
    np.testing.assert_allclose(mean, frame.mean().reindex(range(groups)).to_numpy(), rtol=1e-9, equal_nan=True)
    np.testing.assert_allclose(std, frame.std().reindex(range(groups)).to_numpy(), rtol=1e-6, equal_nan=True)


@pytest.mark.parametrize("backend", BACKENDS)
def test_last_max_and_categories(backend, events):
    codes, values, groups = events
    frame = pd.DataFrame(values).assign(g=codes).query("g >= 0")
    last = kernels.group_last(codes, values, groups, backend=backend)
    np.testing.assert_allclose(last, frame.groupby("g").last().reindex(range(groups)).to_numpy(), equal_nan=True)

    mask = values[:, 0] > 0.5
    got = kernels.group_max_where(codes, values[:, 2], mask, groups, backend=backend)
    want = frame[frame[0] > 0.5].groupby("g")[2].max().reindex(range(groups))
    np.testing.assert_allclose(got, want.to_numpy(), equal_nan=True)

    cats = (np.abs(values[:, 0]) * 2).astype(np.int32)  # some fall outside 0..2 and are ignored
    table = kernels.group_category_counts(codes, cats, groups, 3, backend=backend)
    keep = (codes >= 0) & (cats < 3)
    want = pd.crosstab(codes[keep], cats[keep]).reindex(index=range(groups), columns=range(3), fill_value=0)
    np.testing.assert_array_equal(table, want.to_numpy())


@pytest.mark.parametrize("backend", BACKENDS)
def test_group_join_keeps_row_order(backend):
    codes = np.array([2, 0, 2, -1, 2], dtype=np.int32)
    texts = ["a", "b", "c", "ignored", "d"]
    out = kernels.group_join(codes, texts, 4, backend=backend)
    assert out.tolist() == ["b", "", "a | c | d", ""]


@pytest.mark.parametrize("backend", BACKENDS)
def test_binned_frequencies_match_searchsorted(backend):
    rng = np.random.default_rng(1)
    values = rng.normal(size=5000)
    values[::50] = np.nan
    edges = np.quantile(values[~np.isnan(values)], np.linspace(0, 1, 11)[1:-1])
    values[:5] = edges[:5]  # values exactly on an edge go right, like searchsorted(side="right")
    got = kernels.binned_frequencies(values, edges, backend=backend)
    finite = values[~np.isnan(values)]
    want = np.append(
        np.bincount(np.searchsorted(edges, finite, side="right"), minlength=len(edges) + 1), np.isnan(values).sum()
    ) / len(values)
    np.testing.assert_allclose(got, want)
    assert got.sum() == pytest.approx(1.0)


@pytest.mark.parametrize("backend", COMPILED_PARAMS)
def test_feature_builder_identical_across_backends(backend, monkeypatch):
    data = simulate(SimulationConfig(n_customers=600, new_customers_per_week=4, n_weeks=40), seed=9)
    cfg = FeaturesConfig(tfidf_max_features=100, svd_components=4)
    monkeypatch.setattr(kernels, "_backend", backend)
    compiled_frame = FeatureBuilder(data, cfg, 8).build_many([20, 28])
    monkeypatch.setattr(kernels, "_backend", _kernels_py)
    numpy_frame = FeatureBuilder(data, cfg, 8).build_many([20, 28])
    pd.testing.assert_frame_equal(compiled_frame, numpy_frame, rtol=1e-6)
