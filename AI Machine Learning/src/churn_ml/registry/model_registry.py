"""File-based model registry with versioning, stages and champion/challenger promotion.

Layout::

    registry/
      registry.json            # index: versions, stages, production pointer, history
      v0001/model.joblib       # ChurnModel bundle
      v0001/metrics.json
      v0001/report.html
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from ..logging_utils import get_logger
from ..models.churn_model import ChurnModel

log = get_logger(__name__)

STAGES = ("staging", "production", "archived")


class RegistryError(RuntimeError):
    pass


def _json_default(value: Any):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"not JSON serialisable: {type(value)}")


def write_json(path: Path, payload: Any) -> None:
    """Atomic JSON write (temp file + replace) so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=_json_default)
    os.replace(tmp, path)


class ModelRegistry:
    INDEX = "registry.json"
    MODEL_FILE = "model.joblib"

    def __init__(self, root: Path):
        self.root = Path(root)
        self._cache: dict[int, ChurnModel] = {}

    # ---------------------------------------------------------------- index
    def _read(self) -> dict:
        path = self.root / self.INDEX
        if not path.exists():
            return {"versions": {}, "production": None, "history": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, index: dict) -> None:
        write_json(self.root / self.INDEX, index)

    def version_dir(self, version: int) -> Path:
        return self.root / f"v{version:04d}"

    # ------------------------------------------------------------- register
    def register(
        self,
        model: ChurnModel,
        metrics: dict,
        extra_files: dict[str, str | bytes] | None = None,
        tags: dict[str, Any] | None = None,
    ) -> int:
        index = self._read()
        version = max(map(int, index["versions"]), default=0) + 1
        directory = self.version_dir(version)
        model.metadata["version"] = version
        model.save(directory / self.MODEL_FILE)
        write_json(directory / "metrics.json", metrics)
        for name, content in (extra_files or {}).items():
            target = directory / name
            target.write_bytes(content) if isinstance(content, bytes) else target.write_text(content, encoding="utf-8")
        index["versions"][str(version)] = {
            "version": version,
            "stage": "staging",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "path": directory.relative_to(self.root).as_posix(),
            "test_metrics": {
                k: metrics.get("test", {}).get(k) for k in ("roc_auc", "average_precision", "brier", "campaign_profit")
            },
            "members": model.weights,
            "tags": tags or {},
        }
        self._write(index)
        log.info("registered model v%04d", version)
        return version

    # ----------------------------------------------------------------- read
    def list(self) -> pd.DataFrame:
        rows = []
        for entry in self._read()["versions"].values():
            rows.append(
                {
                    "version": entry["version"],
                    "stage": entry["stage"],
                    "created_at": entry["created_at"],
                    **{f"test_{k}": v for k, v in entry["test_metrics"].items()},
                    "members": ", ".join(entry["members"]),
                }
            )
        return pd.DataFrame(rows).sort_values("version") if rows else pd.DataFrame()

    def production_version(self) -> int | None:
        return self._read()["production"]

    def latest_version(self) -> int | None:
        versions = list(map(int, self._read()["versions"]))
        return max(versions) if versions else None

    def resolve(self, ref: int | str | None = "production") -> int:
        if ref is None or ref == "production":
            version = self.production_version()
            if version is None:
                raise RegistryError("no production model; train one with `churn-ml train`")
            return version
        if ref == "latest":
            version = self.latest_version()
            if version is None:
                raise RegistryError("registry is empty")
            return version
        version = int(ref)
        if str(version) not in self._read()["versions"]:
            raise RegistryError(f"model version {version} does not exist")
        return version

    def load(self, ref: int | str | None = "production") -> ChurnModel:
        version = self.resolve(ref)
        if version not in self._cache:
            self._cache[version] = ChurnModel.load(self.version_dir(version) / self.MODEL_FILE)
        return self._cache[version]

    def metrics(self, ref: int | str | None = "production") -> dict:
        path = self.version_dir(self.resolve(ref)) / "metrics.json"
        return json.loads(path.read_text(encoding="utf-8"))

    # -------------------------------------------------------------- stages
    def promote(self, version: int, reason: str = "manual") -> None:
        index = self._read()
        if str(version) not in index["versions"]:
            raise RegistryError(f"model version {version} does not exist")
        previous = index["production"]
        if previous is not None and previous != version:
            index["versions"][str(previous)]["stage"] = "archived"
        index["versions"][str(version)]["stage"] = "production"
        index["production"] = version
        index["history"].append(
            {
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "production": version,
                "previous": previous,
                "reason": reason,
            }
        )
        self._write(index)
        log.info("promoted v%04d to production (previous: %s, reason: %s)", version, previous, reason)

    def rollback(self) -> int:
        index = self._read()
        current = index["production"]
        # Skip rollback events so repeated rollbacks walk further back instead of toggling.
        for event in reversed(index["history"]):
            if event["reason"].startswith("rollback"):
                continue
            if event["production"] == current and event["previous"] is not None:
                self.promote(event["previous"], reason=f"rollback from v{current:04d}")
                return event["previous"]
        raise RegistryError("nothing to roll back to")

    def champion_challenger(
        self, challenger: ChurnModel, X_eval: pd.DataFrame, y_eval: np.ndarray, tolerance: float
    ) -> dict[str, Any]:
        """Score both models on the challenger's out-of-time test set and decide."""
        challenger_auc = float(roc_auc_score(y_eval, challenger.predict_proba(X_eval)))
        try:
            champion = self.load("production")
        except RegistryError:
            return {
                "promote": True,
                "reason": "no production model yet",
                "challenger_auc": challenger_auc,
                "champion_auc": None,
            }
        try:
            champion_auc = float(roc_auc_score(y_eval, champion.predict_proba(X_eval)))
        except Exception as exc:  # incompatible feature schema etc.
            return {
                "promote": True,
                "reason": f"champion could not score the evaluation set ({exc})",
                "challenger_auc": challenger_auc,
                "champion_auc": None,
            }
        promote = challenger_auc >= champion_auc - tolerance
        verdict = "challenger wins" if promote else "champion retained"
        return {
            "promote": promote,
            "reason": f"{verdict}: {challenger_auc:.4f} vs {champion_auc:.4f}",
            "challenger_auc": challenger_auc,
            "champion_auc": champion_auc,
            "champion_version": champion.metadata.get("version"),
        }
