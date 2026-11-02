"""Raw-data loading and cached feature datasets."""

from __future__ import annotations

import hashlib
import json

import pandas as pd

from ..data.simulator import SimulatedData, simulate
from ..features.builder import FeatureBuilder
from ..features.spec import FeatureSpec
from ..logging_utils import get_logger, timed
from ..settings import Settings

log = get_logger(__name__)


def simulate_and_save(settings: Settings) -> SimulatedData:
    with timed(log, "simulating raw tables"):
        data = simulate(settings.simulation, settings.project.seed)
    data.save(settings.raw_dir)
    (settings.raw_dir / "fingerprint.txt").write_text(raw_fingerprint(settings), encoding="utf-8")
    return data


def load_raw(settings: Settings, simulate_if_missing: bool = False) -> SimulatedData:
    try:
        return SimulatedData.load(settings.raw_dir)
    except FileNotFoundError:
        if not simulate_if_missing:
            raise
        return simulate_and_save(settings)


def raw_fingerprint(settings: Settings) -> str:
    payload = {"simulation": settings.simulation.model_dump(mode="json"), "seed": settings.project.seed}
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def feature_fingerprint(settings: Settings) -> str:
    payload = {
        "raw": raw_fingerprint(settings),
        "features": settings.features.model_dump(mode="json"),
        "labeling": settings.labeling.model_dump(mode="json"),
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def build_training_frame(
    settings: Settings, data: SimulatedData, use_cache: bool = True
) -> tuple[pd.DataFrame, FeatureSpec]:
    """All labelled snapshots, cached on disk by a fingerprint of the configuration."""
    spec = FeatureSpec.from_config(settings.features)
    path = settings.features_dir / f"training_{feature_fingerprint(settings)}.parquet"
    if use_cache and path.exists():
        log.info("using cached features %s", path.name)
        return pd.read_parquet(path), spec
    builder = FeatureBuilder(data, settings.features, settings.labeling.horizon_weeks)
    weeks = settings.labelled_snapshots()
    with timed(log, f"building features for {len(weeks)} snapshots"):
        frame = builder.build_many(weeks)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return frame, spec


def build_scoring_frame(settings: Settings, data: SimulatedData, week: int | None = None) -> tuple[pd.DataFrame, int]:
    """Feature rows for every active customer as of ``week`` (default: end of history)."""
    builder = FeatureBuilder(data, settings.features, settings.labeling.horizon_weeks)
    week = builder.n_weeks if week is None else int(week)
    if not 0 < week <= builder.n_weeks:
        raise ValueError(f"week must be in 1..{builder.n_weeks}, got {week}")
    return builder.build_snapshot(week), week
