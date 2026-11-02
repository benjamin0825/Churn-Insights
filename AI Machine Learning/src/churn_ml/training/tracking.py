"""Thin MLflow wrapper that becomes a no-op when tracking is disabled."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..logging_utils import get_logger
from ..settings import Settings

log = get_logger(__name__)


def _flatten(prefix: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten(f"{prefix}.{k}" if prefix else str(k), v, out)
    else:
        out[prefix] = value


class Tracker:
    def __init__(self, settings: Settings):
        self.enabled = settings.tracking.enabled
        self.settings = settings
        self._mlflow = None

    @contextmanager
    def run(self, name: str) -> Iterator[Tracker]:
        if not self.enabled:
            yield self
            return
        os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
        import mlflow

        self._mlflow = mlflow
        self.settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
        mlflow.set_tracking_uri(self.settings.resolve_uri(self.settings.tracking.uri))
        mlflow.set_experiment(self.settings.tracking.experiment)
        with mlflow.start_run(run_name=name):
            yield self
        self._mlflow = None

    def log_params(self, params: dict[str, Any]) -> None:
        if self._mlflow:
            flat: dict[str, Any] = {}
            _flatten("", params, flat)
            self._mlflow.log_params({k: str(v)[:500] for k, v in flat.items()})

    def log_metrics(self, metrics: dict[str, Any], prefix: str = "") -> None:
        if self._mlflow:
            flat: dict[str, Any] = {}
            _flatten(prefix, metrics, flat)
            numeric = {
                k.replace("@", "_at_"): float(v)
                for k, v in flat.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            }
            self._mlflow.log_metrics(numeric)

    def set_tags(self, tags: dict[str, Any]) -> None:
        if self._mlflow:
            self._mlflow.set_tags({k: str(v) for k, v in tags.items()})

    def log_artifact(self, path: Path) -> None:
        if self._mlflow and Path(path).exists():
            self._mlflow.log_artifact(str(path))
