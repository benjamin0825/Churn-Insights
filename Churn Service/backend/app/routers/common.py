"""Helpers shared by the routers."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException, status

from ..workspace import Workspace


def clean(value: Any) -> Any:
    """Make a value JSON-safe: NaN/inf -> None, NumPy scalars -> Python, timestamps -> ISO strings."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        f = float(value)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp,)):
        return None if pd.isna(value) else value.isoformat()
    if value is pd.NA or value is pd.NaT:
        return None
    return value


def records(frame: pd.DataFrame) -> list[dict]:
    return [clean(row) for row in frame.to_dict(orient="records")]


def require_scores(ws: Workspace) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    scores, features, meta = ws.latest_scores(), ws.latest_features(), ws.latest_meta()
    if scores is None or features is None or meta is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No scores yet: load data and train a model first")
    return scores, features, meta
