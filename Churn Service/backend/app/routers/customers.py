"""At-risk customer list and customer detail."""

from __future__ import annotations

from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from ..campaigns import customer_table
from ..models import User
from ..security import current_user
from ..names import demo_name
from ..workspace import Workspace
from .common import clean, records, require_scores

router = APIRouter(prefix="/api/customers", tags=["customers"])

SORTS = {"probability": "churn_probability", "revenue": "expected_revenue_at_risk", "tenure": "tenure_weeks",
         "charge": "current_charge", "id": "customer_id"}
LIST_COLUMNS = ["customer_id", "churn_probability", "risk_tier", "target_for_retention", "expected_revenue_at_risk",
                "region", "plan", "contract_type", "internet_service", "tenure_weeks", "current_charge", "top_reasons"]
DETAIL_FEATURES = [
    ("Usage", ["sessions_mean_4w", "sessions_mean_12w", "minutes_mean_4w", "minutes_mean_12w", "sessions_trend",
               "minutes_trend", "weeks_since_active", "active_week_ratio_12w"]),
    ("Billing", ["current_charge", "discount_pct", "charge_change_12w", "late_payments_26w", "avg_days_late_26w"]),
    ("Support", ["tickets_4w", "tickets_12w", "billing_tickets_12w", "technical_tickets_12w",
                 "cancellation_tickets_12w", "avg_csat_12w", "avg_resolution_hours_12w", "weeks_since_ticket"]),
    ("Profile", ["age", "tenure_weeks", "dependents", "has_streaming", "paperless_billing"]),
]


def _start_date(ws: Workspace) -> pd.Timestamp:
    import json

    meta = ws.raw_dir / "meta.json"
    start = json.loads(meta.read_text(encoding="utf-8")).get("start_date") if meta.exists() else None
    return pd.Timestamp(start or "2024-01-01")


@router.get("")
def list_customers(
    tier: list[Literal["high", "medium", "low"]] = Query(default=[]),
    region: list[str] = Query(default=[]),
    plan: list[str] = Query(default=[]),
    contract: list[str] = Query(default=[]),
    search: str | None = Query(default=None, max_length=40),
    targeted_only: bool = False,
    sort: Literal["probability", "revenue", "tenure", "charge", "id"] = "probability",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=5, le=200),
    user: User = Depends(current_user),
) -> dict:
    ws = Workspace(user.organization_id)
    scores, features, meta = require_scores(ws)
    table = customer_table(scores, features)
    facets = {c: sorted(table[c].dropna().astype(str).unique().tolist()) for c in ("region", "plan", "contract_type")}

    mask = pd.Series(True, index=table.index)
    if tier:
        mask &= table["risk_tier"].isin(tier)
    if region:
        mask &= table["region"].isin(region)
    if plan:
        mask &= table["plan"].isin(plan)
    if contract:
        mask &= table["contract_type"].isin(contract)
    if targeted_only:
        mask &= table["target_for_retention"]
    if search:
        needle = search.strip()
        found = table["customer_id"].astype(str).str.contains(needle, regex=False)
        if ws.is_demo():
            names = table["customer_id"].map(demo_name)
            found |= names.str.lower().str.contains(needle.lower(), regex=False)
        mask &= found
    filtered = table[mask].sort_values(SORTS[sort], ascending=order == "asc", kind="stable")

    start = (page - 1) * page_size
    items = filtered.iloc[start:start + page_size][LIST_COLUMNS]
    return {"total": int(len(filtered)), "page": page, "page_size": page_size, "as_of_week": meta["week"],
            "model_version": meta["model_version"], "facets": facets,
            "items": [{**row, "name": ws.customer_name(row["customer_id"])} for row in records(items)]}


@router.get("/{customer_id}")
def customer_detail(customer_id: int, user: User = Depends(current_user)) -> dict:
    ws = Workspace(user.organization_id)
    scores, features, meta = require_scores(ws)
    feature_row = features[features["customer_id"] == customer_id]
    if feature_row.empty:
        raise HTTPException(404, "Customer not found among currently active customers")
    score = scores[scores["customer_id"] == customer_id].iloc[0]

    explainer = ws.explainer(meta["model_version"])
    reasons = explainer.reasons(feature_row, top_n=8)[0] if explainer is not None else []
    row = feature_row.iloc[0]

    raw = ws.raw()
    start = _start_date(ws)

    def dated(frame: pd.DataFrame, columns: list[str]) -> list[dict]:
        out = frame[columns].copy()
        out.insert(1, "date", (start + pd.to_timedelta(out["week"].astype(int) * 7, unit="D")).dt.date.astype(str))
        return records(out)

    usage = raw.usage[raw.usage["customer_id"] == customer_id].sort_values("week")
    billing = raw.billing[raw.billing["customer_id"] == customer_id].sort_values("week")
    tickets = raw.tickets[raw.tickets["customer_id"] == customer_id].sort_values("week", ascending=False)
    customer = raw.customers[raw.customers["customer_id"] == customer_id].iloc[0]

    return clean({
        "customer_id": customer_id,
        "name": ws.customer_name(customer_id),
        "as_of_week": meta["week"],
        "model_version": meta["model_version"],
        "score": {k: score[k] for k in ("churn_probability", "risk_tier", "target_for_retention",
                                        "expected_revenue_at_risk")},
        "profile": {
            "region": row["region"], "plan": row["plan"], "contract_type": row["contract_type"],
            "internet_service": row["internet_service"], "payment_method": row["payment_method"],
            "acquisition_channel": row["acquisition_channel"], "age": row["age"],
            "tenure_weeks": row["tenure_weeks"], "current_charge": row["current_charge"],
            "signup_date": str(pd.Timestamp(customer["signup_date"]).date()),
        },
        "reasons": reasons,
        "features": [{"group": group, "items": [{"name": f, "value": row[f]} for f in names if f in row]}
                     for group, names in DETAIL_FEATURES],
        "history": {
            "usage": dated(usage.tail(52), ["week", "sessions", "minutes", "data_gb"]),
            "billing": dated(billing.tail(13), ["week", "amount", "discount_pct", "paid_late", "days_late"]),
            "tickets": dated(tickets.head(20), ["week", "category", "text", "resolution_hours", "csat"]),
        },
    })
