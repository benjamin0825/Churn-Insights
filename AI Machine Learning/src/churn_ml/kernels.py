"""Kernel dispatch for feature engineering and drift monitoring.

Three interchangeable implementations share one API (see ``docs/native-kernels.md``):

* ``ext``    -- ``churn_ml._kernels_ext``, the open-source compiled module built from
  ``src/churn_ml/_kernels_ext.pyx`` (or ``.c``) with ``scripts/build_native.py``;
* ``native`` -- ``churn_ml._native``, the binary-only native engine shipped with the package;
* ``numpy``  -- ``churn_ml._kernels_py``, the pure-NumPy implementation and behavioural spec.

``CHURN_ML_KERNELS=auto`` (default) uses the first that imports, in that order. Set it to
``ext``, ``native`` or ``numpy`` to force one. Inputs are coerced here so every backend sees
C-contiguous int32 / float64 arrays.
"""

from __future__ import annotations

import importlib
import os

import numpy as np

from . import _kernels_py

_MODULES = {"ext": "churn_ml._kernels_ext", "native": "churn_ml._native"}


def load_backend(name: str):
    """Import one backend by name; raises ImportError when it isn't available."""
    if name == "numpy":
        return _kernels_py
    if name not in _MODULES:
        raise ValueError(f"unknown kernel backend {name!r}; use auto, ext, native or numpy")
    return importlib.import_module(_MODULES[name])


def available_backends() -> dict[str, object]:
    found = {}
    for name in ("ext", "native", "numpy"):
        try:
            found[name] = load_backend(name)
        except ImportError:
            pass
    return found


_choice = os.environ.get("CHURN_ML_KERNELS", "auto").strip().lower()
if _choice == "auto":
    BACKEND, _backend = next(iter(available_backends().items()))
else:
    BACKEND, _backend = _choice, load_backend(_choice)
NATIVE_AVAILABLE = BACKEND != "numpy"


def _codes(codes) -> np.ndarray:
    return np.ascontiguousarray(codes, dtype=np.int32)


def _matrix(values) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    return np.ascontiguousarray(arr.reshape(-1, 1) if arr.ndim == 1 else arr)


def group_stats(codes, values, n_groups: int, backend=None):
    """Per-group (sums, sums of squares, counts); ``values`` is 1-D or (rows, k)."""
    return (backend or _backend).group_stats(_codes(codes), _matrix(values), int(n_groups))


def group_last(codes, values, n_groups: int, backend=None):
    return (backend or _backend).group_last(_codes(codes), _matrix(values), int(n_groups))


def group_max_where(codes, values, mask, n_groups: int, backend=None):
    return (backend or _backend).group_max_where(
        _codes(codes),
        np.ascontiguousarray(values, dtype=np.float64),
        np.ascontiguousarray(mask, dtype=np.uint8),
        int(n_groups),
    )


def group_category_counts(codes, categories, n_groups: int, n_categories: int, backend=None):
    return (backend or _backend).group_category_counts(
        _codes(codes), np.ascontiguousarray(categories, dtype=np.int32), int(n_groups), int(n_categories)
    )


def group_join(codes, texts, n_groups: int, sep: str = " | ", backend=None):
    return (backend or _backend).group_join(_codes(codes), list(texts), int(n_groups), sep)


def binned_frequencies(values, edges, backend=None):
    return (backend or _backend).binned_frequencies(
        np.ascontiguousarray(values, dtype=np.float64), np.ascontiguousarray(edges, dtype=np.float64)
    )


def group_mean_std(codes, values, n_groups: int, backend=None):
    """Per-group mean and sample std (ddof=1, NaN for fewer than two rows), like pandas."""
    sums, sumsq, counts = group_stats(codes, values, n_groups, backend)
    n = counts[:, None].astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = sums / n
        var = np.clip((sumsq - sums * sums / n) / (n - 1), 0, None)
    std = np.sqrt(var)
    std[(counts < 2)] = np.nan
    return mean, std, counts
