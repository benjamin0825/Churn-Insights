"""Standard benchmark workloads for the kernel backends.

``scripts/benchmark_native.py`` times each available backend (``ext``, ``native``,
``numpy``) on these workloads. Speed is reported as a speed-up over the NumPy kernels on
the same machine, which carries over between machines far better than raw seconds.
``benchmarks/engine_baseline.json`` records the bundled engine's speed-ups, for
platforms where its pre-built binary can't be loaded.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from . import _kernels_py, kernels

BASELINE_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "engine_baseline.json"
FEATURE_BUILD = "feature_build"
NUMPY_BACKEND = _kernels_py


def workloads(quick: bool = False) -> dict[str, dict]:
    rng = np.random.default_rng(7)
    n, groups = (500_000, 20_000) if quick else (5_000_000, 200_000)
    codes = rng.integers(0, groups, n).astype(np.int32)
    values = rng.normal(size=(n, 3))
    texts = list(np.array(["router keeps restarting", "bill went up", "thanks"])[rng.integers(0, 3, n // 10)])
    big = rng.normal(size=n)
    edges = np.quantile(big[:100_000], np.linspace(0, 1, 11)[1:-1])
    return {
        "group_stats": dict(codes=codes, values=values, n_groups=groups),
        "group_last": dict(codes=codes, values=values, n_groups=groups),
        "group_max_where": dict(codes=codes, values=values[:, 0], mask=values[:, 1] > 0, n_groups=groups),
        "group_category_counts": dict(
            codes=codes, categories=rng.integers(0, 3, n).astype(np.int32), n_groups=groups, n_categories=3
        ),
        "group_join": dict(codes=codes[: n // 10], texts=texts, n_groups=groups),
        "binned_frequencies": dict(values=big, edges=edges),
    }


def best_time(call: Callable[[], object], repeat: int) -> float | None:
    """Best wall time of ``repeat`` runs, or None if the call fails."""
    try:
        best = math.inf
        for _ in range(repeat):
            start = time.perf_counter()
            call()
            best = min(best, time.perf_counter() - start)
        return best
    except Exception:
        return None


def _feature_builder(quick: bool):
    from .data.simulator import simulate
    from .features import FeatureBuilder
    from .settings import FeaturesConfig, SimulationConfig

    size = (
        dict(n_customers=1500, new_customers_per_week=8) if quick else dict(n_customers=6000, new_customers_per_week=30)
    )
    data = simulate(SimulationConfig(n_weeks=80, **size), seed=3)
    return FeatureBuilder(data, FeaturesConfig(), 8)


def run(backends: dict[str, object], repeat: int = 5, quick: bool = False) -> dict[str, dict[str, float | None]]:
    """Seconds per task for each backend module: ``{task: {backend_name: seconds}}``."""
    results: dict[str, dict[str, float | None]] = {}
    for name, kwargs in workloads(quick).items():
        fn = getattr(kernels, name)
        results[name] = {
            label: best_time(lambda fn=fn, module=module, kwargs=kwargs: fn(backend=module, **kwargs), repeat)
            for label, module in backends.items()
        }

    builder = _feature_builder(quick)
    weeks = list(range(28, 73, 4))
    results[FEATURE_BUILD] = {}
    previous = kernels._backend
    try:
        for label, module in backends.items():
            kernels._backend = module
            results[FEATURE_BUILD][label] = best_time(lambda: builder.build_many(weeks), max(1, repeat // 2))
    finally:
        kernels._backend = previous
    return results


def speedups(results: dict[str, dict[str, float | None]], backend: str) -> dict[str, float | None]:
    """Speed-up of ``backend`` over NumPy per task (None where either run failed)."""
    out = {}
    for task, row in results.items():
        base, mine = row.get("numpy"), row.get(backend)
        out[task] = base / mine if base and mine else None
    return out


def overall(per_task: dict[str, float | None]) -> float | None:
    """Geometric mean of per-task speed-ups: every kernel counts equally. None if any task failed."""
    values = list(per_task.values())
    if not values or any(v is None for v in values):
        return None
    return math.exp(sum(math.log(v) for v in values) / len(values))
