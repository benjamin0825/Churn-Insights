"""Typed configuration loaded from YAML, with profile merging and CLI overrides."""

from __future__ import annotations

import copy
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "configs"
DEFAULT_CONFIG = CONFIG_DIR / "default.yaml"


class ProjectConfig(BaseModel):
    name: str = "churn-ml"
    seed: int = 42


class PathsConfig(BaseModel):
    artifacts: Path = Path("artifacts")


class DriftConfig(BaseModel):
    enabled: bool = True
    start_week: int = 98
    region: str = "west"
    satisfaction_shock: float = 0.08
    usage_drop: float = Field(0.3, ge=0, lt=1)


class SimulationConfig(BaseModel):
    n_customers: int = Field(10000, gt=0)
    new_customers_per_week: float = Field(60, ge=0)
    n_weeks: int = Field(104, gt=8)
    start_date: date = date(2024, 1, 1)
    drift: DriftConfig = DriftConfig()


class LabelingConfig(BaseModel):
    horizon_weeks: int = Field(8, gt=0)
    first_snapshot_week: int = Field(28, gt=0)
    snapshot_every_weeks: int = Field(4, gt=0)


class FeaturesConfig(BaseModel):
    windows_weeks: list[int] = [4, 12]
    text_window_weeks: int = 12
    tfidf_max_features: int = 3000
    svd_components: int = 16


class SplitConfig(BaseModel):
    validation_snapshots: int = Field(2, gt=0)
    test_snapshots: int = Field(2, gt=0)


ModelName = Literal["logistic_regression", "random_forest", "lightgbm", "xgboost", "tabular_nn"]


class ModelsConfig(BaseModel):
    enabled: list[ModelName] = ["logistic_regression", "random_forest", "lightgbm", "xgboost", "tabular_nn"]

    @field_validator("enabled")
    @classmethod
    def _non_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("at least one model must be enabled")
        return value


class TuningConfig(BaseModel):
    metric: Literal["average_precision", "roc_auc"] = "average_precision"
    sample_rows: int | None = 60000
    timeout_seconds: int = 1800
    storage: str | None = None
    n_trials: dict[str, int] = {}


class EnsembleConfig(BaseModel):
    enabled: bool = True
    top_k: int = Field(3, gt=0)


class CalibrationConfig(BaseModel):
    method: Literal["isotonic", "sigmoid", "none"] = "isotonic"


class BusinessConfig(BaseModel):
    offer_cost: float = Field(15.0, ge=0)
    retention_success_rate: float = Field(0.35, ge=0, le=1)
    months_of_value: float = Field(12, gt=0)


class RegistryConfig(BaseModel):
    auto_promote: bool = True
    tolerance: float = 0.005


class MonitoringConfig(BaseModel):
    psi_warning: float = 0.10
    psi_alert: float = 0.25
    reference_sample: int = 20000
    segment_column: str | None = "region"


class ExplainConfig(BaseModel):
    background_rows: int = 2000
    top_reasons: int = 5


class TrackingConfig(BaseModel):
    enabled: bool = True
    uri: str = "sqlite:///{artifacts}/mlflow.db"
    experiment: str = "churn-ml"


class ServingConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000


class Settings(BaseModel):
    project: ProjectConfig = ProjectConfig()
    paths: PathsConfig = PathsConfig()
    simulation: SimulationConfig = SimulationConfig()
    labeling: LabelingConfig = LabelingConfig()
    features: FeaturesConfig = FeaturesConfig()
    split: SplitConfig = SplitConfig()
    models: ModelsConfig = ModelsConfig()
    tuning: TuningConfig = TuningConfig()
    ensemble: EnsembleConfig = EnsembleConfig()
    calibration: CalibrationConfig = CalibrationConfig()
    business: BusinessConfig = BusinessConfig()
    registry: RegistryConfig = RegistryConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    explain: ExplainConfig = ExplainConfig()
    tracking: TrackingConfig = TrackingConfig()
    serving: ServingConfig = ServingConfig()

    # ---- derived paths -------------------------------------------------
    @property
    def artifacts_dir(self) -> Path:
        path = self.paths.artifacts
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def raw_dir(self) -> Path:
        return self.artifacts_dir / "raw"

    @property
    def features_dir(self) -> Path:
        return self.artifacts_dir / "features"

    @property
    def registry_dir(self) -> Path:
        return self.artifacts_dir / "registry"

    @property
    def predictions_dir(self) -> Path:
        return self.artifacts_dir / "predictions"

    @property
    def monitoring_dir(self) -> Path:
        return self.artifacts_dir / "monitoring"

    def resolve_uri(self, uri: str | None) -> str | None:
        """Expand the ``{artifacts}`` placeholder used by sqlite URIs."""
        if uri is None:
            return None
        return uri.replace("{artifacts}", self.artifacts_dir.as_posix())

    def last_labelled_snapshot(self) -> int:
        """Latest snapshot week whose label window fits inside the simulated history."""
        lab = self.labeling
        last_allowed = self.simulation.n_weeks - lab.horizon_weeks
        steps = (last_allowed - lab.first_snapshot_week) // lab.snapshot_every_weeks
        return lab.first_snapshot_week + steps * lab.snapshot_every_weeks

    def labelled_snapshots(self) -> list[int]:
        lab = self.labeling
        return list(range(lab.first_snapshot_week, self.last_labelled_snapshot() + 1, lab.snapshot_every_weeks))


def _deep_merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _apply_override(tree: dict, dotted: str) -> None:
    """Apply one ``a.b.c=value`` override; the value is parsed as YAML."""
    if "=" not in dotted:
        raise ValueError(f"Override must look like key.path=value, got {dotted!r}")
    key, raw = dotted.split("=", 1)
    parts = key.strip().split(".")
    node = tree
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = yaml.safe_load(raw)


def _resolve_profile(profile: str | Path) -> Path:
    path = Path(profile)
    if path.suffix in {".yaml", ".yml"} and path.exists():
        return path
    candidate = CONFIG_DIR / f"{profile}.yaml"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Config profile {profile!r} not found (looked in {CONFIG_DIR})")


def load_settings(
    profile: str | Path | None = None, overrides: list[str] | None = None, extra: dict[str, Any] | None = None
) -> Settings:
    """Load default.yaml, merge a profile (name in configs/ or a path), then overrides."""
    tree = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8")) or {}
    if profile and str(profile) != "default":
        tree = _deep_merge(tree, yaml.safe_load(_resolve_profile(profile).read_text(encoding="utf-8")) or {})
    if extra:
        tree = _deep_merge(tree, extra)
    for item in overrides or []:
        _apply_override(tree, item)
    return Settings.model_validate(tree)
