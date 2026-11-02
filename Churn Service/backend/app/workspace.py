"""Per-organization ML workspace on top of the ``churn_ml`` library.

Each organization gets its own artifacts directory (raw tables, feature cache, model
registry, predictions, drift reports). Directory names are derived from the numeric
organization id only, never from user input.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd
from churn_ml.data.simulator import SimulatedData
from churn_ml.explain.shap_explainer import try_explainer
from churn_ml.registry import ModelRegistry, RegistryError
from churn_ml.settings import Settings, load_settings

from .config import get_settings

# Training presets offered in the UI: churn_ml profile + overrides.
TRAINING_PROFILES: dict[str, tuple[str, list[str]]] = {
    "quick": ("fast", ["models.enabled=[logistic_regression, lightgbm, xgboost]"]),
    "standard": ("fast", ["tuning.n_trials.lightgbm=15", "tuning.n_trials.xgboost=10", "tuning.n_trials.tabular_nn=4",
                          "tuning.sample_rows=40000"]),
    "thorough": ("default", []),
}

LATEST_SCORES = "latest_scores.parquet"
LATEST_FEATURES = "latest_features.parquet"
LATEST_META = "latest_scoring.json"

_org_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def org_lock(org_id: int) -> threading.Lock:
    """One heavy job (training, data load) per organization at a time."""
    with _locks_guard:
        return _org_locks.setdefault(org_id, threading.Lock())


@dataclass
class Workspace:
    org_id: int

    @property
    def root(self) -> Path:
        return get_settings().orgs_dir / f"org_{int(self.org_id):06d}"

    def settings(self, profile: str = "quick", n_weeks: int | None = None) -> Settings:
        base, overrides = TRAINING_PROFILES.get(profile, TRAINING_PROFILES["quick"])
        extra = [
            f"paths.artifacts={(self.root / 'artifacts').as_posix()}",
            "tracking.enabled=false",
            "tuning.storage=null",
            *overrides,
        ]
        weeks = n_weeks if n_weeks is not None else self.n_weeks()
        if weeks:
            extra.append(f"simulation.n_weeks={weeks}")  # label windows must fit the real history
        return load_settings(base, extra)

    # ----------------------------------------------------------- raw data
    @property
    def raw_dir(self) -> Path:
        return self.root / "artifacts" / "raw"

    def has_data(self) -> bool:
        return all((self.raw_dir / f"{t}.parquet").exists() for t in SimulatedData.TABLES)

    def raw(self) -> SimulatedData:
        return _load_raw(str(self.raw_dir), _mtime(self.raw_dir / "usage.parquet"))

    def is_demo(self) -> bool:
        """True when the active data is the generated demo dataset (not a customer's upload)."""
        meta = self.raw_dir / "meta.json"
        return meta.exists() and json.loads(meta.read_text(encoding="utf-8")).get("source") == "demo"

    def customer_name(self, customer_id: int) -> str | None:
        """A display name: invented for demo customers, None for uploaded data (we never invent names for real people)."""
        from .names import demo_name

        return demo_name(customer_id) if self.is_demo() else None

    def n_weeks(self) -> int | None:
        meta = self.raw_dir / "meta.json"
        if meta.exists():
            return int(json.loads(meta.read_text(encoding="utf-8"))["n_weeks"])
        return None

    def save_raw(self, data: SimulatedData, meta: dict) -> None:
        data.save(self.raw_dir)
        (self.raw_dir / "meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
        _load_raw.cache_clear()
        # A new dataset invalidates cached features and the latest scores.
        features = self.root / "artifacts" / "features"
        for cached in features.glob("*.parquet") if features.exists() else []:
            cached.unlink()
        for name in (LATEST_SCORES, LATEST_FEATURES, LATEST_META):
            (self.predictions_dir / name).unlink(missing_ok=True)

    # ------------------------------------------------------------- models
    @property
    def registry(self) -> ModelRegistry:
        return ModelRegistry(self.root / "artifacts" / "registry")

    def production_version(self) -> int | None:
        try:
            return self.registry.resolve("production")
        except RegistryError:
            return None

    def model(self, version: int | str = "production"):
        resolved = self.registry.resolve(version)
        path = self.registry.version_dir(resolved) / ModelRegistry.MODEL_FILE
        return _load_model(str(path), _mtime(path))

    def explainer(self, version: int | str = "production"):
        resolved = self.registry.resolve(version)
        path = self.registry.version_dir(resolved) / ModelRegistry.MODEL_FILE
        return _load_explainer(str(path), _mtime(path))

    # ------------------------------------------------------------- scores
    @property
    def predictions_dir(self) -> Path:
        return self.root / "artifacts" / "predictions"

    @property
    def monitoring_dir(self) -> Path:
        return self.root / "artifacts" / "monitoring"

    def latest_scores(self) -> pd.DataFrame | None:
        path = self.predictions_dir / LATEST_SCORES
        return _read_parquet(str(path), _mtime(path)) if path.exists() else None

    def latest_features(self) -> pd.DataFrame | None:
        path = self.predictions_dir / LATEST_FEATURES
        return _read_parquet(str(path), _mtime(path)) if path.exists() else None

    def latest_meta(self) -> dict | None:
        path = self.predictions_dir / LATEST_META
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def latest_drift(self) -> dict | None:
        reports = sorted(self.monitoring_dir.glob("drift_week*_v*.json")) if self.monitoring_dir.exists() else []
        if not reports:
            return None
        newest = max(reports, key=lambda p: p.stat().st_mtime)
        payload = json.loads(newest.read_text(encoding="utf-8"))
        payload["report_file"] = newest.name
        return payload


# ------------------------------------------------------------- caches
# Keyed by (path, mtime) so a rewritten file is reloaded automatically.
def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


@lru_cache(maxsize=8)
def _load_raw(directory: str, _mtime_key: float) -> SimulatedData:
    return SimulatedData.load(Path(directory))


@lru_cache(maxsize=16)
def _read_parquet(path: str, _mtime_key: float) -> pd.DataFrame:
    return pd.read_parquet(path)


@lru_cache(maxsize=8)
def _load_model(path: str, _mtime_key: float):
    from churn_ml.models import ChurnModel

    return ChurnModel.load(Path(path))


@lru_cache(maxsize=8)
def _load_explainer(path: str, _mtime_key: float):
    return try_explainer(_load_model(path, _mtime_key))
