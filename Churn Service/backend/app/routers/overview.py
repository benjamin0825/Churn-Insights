"""Subscription metrics overview: metric cards with trends, revenue breakdown, activity, churn forecast."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status

from ..metrics import overview
from ..models import User
from ..security import current_user
from ..workspace import Workspace
from .common import clean

router = APIRouter(prefix="/api/overview", tags=["overview"])
PERIODS = {"12w": 12, "26w": 26, "52w": 52, "all": 10_000}


@router.get("")
def get_overview(period: Literal["12w", "26w", "52w", "all"] = "26w", user: User = Depends(current_user)) -> dict:
    ws = Workspace(user.organization_id)
    if not ws.has_data():
        raise HTTPException(status.HTTP_409_CONFLICT, "No data yet: upload CSVs or load the demo dataset")
    body = overview(ws, PERIODS[period])
    for event in body.get("activity", []):
        event["name"] = ws.customer_name(event["customer_id"])

    scores, meta = ws.latest_scores(), ws.latest_meta()
    if scores is not None and meta is not None:
        tiers = scores["risk_tier"].value_counts()
        body["forecast"] = {
            "model_version": meta["model_version"],
            "expected_churners": float(scores["churn_probability"].sum()),
            "revenue_at_risk": float(scores["expected_revenue_at_risk"].sum()),
            "high_risk": int(tiers.get("high", 0)),
            "medium_risk": int(tiers.get("medium", 0)),
            "recommended_for_offer": int(scores["target_for_retention"].sum()),
            "customers": int(len(scores)),
        }
    else:
        body["forecast"] = None
    return clean(body)
