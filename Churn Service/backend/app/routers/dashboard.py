"""Dashboard summary: KPIs, risk breakdowns, churn trend, top drivers, model health."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends

from ..campaigns import customer_table
from ..models import User
from ..security import current_user
from ..workspace import Workspace
from .common import clean, require_scores

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
TIERS = ["high", "medium", "low"]


def _breakdown(table: pd.DataFrame, column: str) -> list[dict]:
    grouped = table.groupby(column).agg(
        customers=("customer_id", "size"),
        avg_probability=("churn_probability", "mean"),
        high_risk=("risk_tier", lambda s: int((s == "high").sum())),
        revenue_at_risk=("expected_revenue_at_risk", "sum"),
    ).reset_index().rename(columns={column: "segment"})
    return grouped.sort_values("avg_probability", ascending=False).to_dict(orient="records")


def _churn_trend(ws: Workspace) -> list[dict]:
    cache = sorted((ws.root / "artifacts" / "features").glob("training_*.parquet"))
    if not cache:
        return []
    labels = pd.read_parquet(max(cache, key=lambda p: p.stat().st_mtime), columns=["snapshot_week", "churned"])
    trend = labels.groupby("snapshot_week")["churned"].agg(["mean", "size"]).reset_index()
    return [{"week": int(r.snapshot_week), "churn_rate": float(r["mean"]), "customers": int(r["size"])}
            for _, r in trend.iterrows()]


@router.get("")
def dashboard(user: User = Depends(current_user)) -> dict:
    ws = Workspace(user.organization_id)
    scores, features, meta = require_scores(ws)
    table = customer_table(scores, features)
    metrics = ws.registry.metrics(meta["model_version"])
    test = metrics.get("test", {})
    tiers = table["risk_tier"].value_counts()
    drift = ws.latest_drift()

    return clean({
        "as_of_week": meta["week"],
        "scored_at": meta["scored_at"],
        "model_version": meta["model_version"],
        "kpis": {
            "customers": int(len(table)),
            "high_risk": int(tiers.get("high", 0)),
            "recommended_for_offer": int(table["target_for_retention"].sum()),
            "expected_churners_8w": float(table["churn_probability"].sum()),
            "revenue_at_risk": float(table["expected_revenue_at_risk"].sum()),
            "avg_churn_probability": float(table["churn_probability"].mean()),
        },
        "tiers": [{"tier": t, "customers": int(tiers.get(t, 0)),
                   "revenue_at_risk": float(table.loc[table["risk_tier"] == t, "expected_revenue_at_risk"].sum())}
                  for t in TIERS],
        "by_region": _breakdown(table, "region"),
        "by_contract": _breakdown(table, "contract_type"),
        "by_plan": _breakdown(table, "plan"),
        "churn_trend": _churn_trend(ws),
        "drivers": [{"feature": k, "importance": v} for k, v in list(metrics.get("global_importance", {}).items())[:10]],
        "model": {k: test.get(k) for k in ("roc_auc", "average_precision", "lift_at_10pct", "ece", "brier",
                                           "campaign_profit", "profit_if_target_all")},
        "drift": None if drift is None else {"status": drift["status"], "week": drift.get("report_file")},
    })
