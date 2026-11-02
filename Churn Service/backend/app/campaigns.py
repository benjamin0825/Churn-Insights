"""Retention campaign planning on top of the latest churn scores.

Expected value of making an offer to customer i:

    EV_i = p_i * success_rate * monthly_charge_i * months_of_value - offer_cost

Customers are ranked by EV and targeted while EV > 0, within the budget and the
customer cap. The summary reports expected (not guaranteed) outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

PROFILE_COLUMNS = ["region", "plan", "contract_type", "internet_service", "tenure_weeks", "current_charge"]


@dataclass(frozen=True)
class CampaignParams:
    offer_cost: float
    retention_success_rate: float
    months_of_value: float
    budget: float | None = None
    max_customers: int | None = None
    risk_tiers: tuple[str, ...] = ("high", "medium", "low")
    min_probability: float = 0.0


def customer_table(scores: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    """Latest scores joined with the profile columns shown in the UI."""
    profile = features[["customer_id", *PROFILE_COLUMNS]]
    return scores.merge(profile, on="customer_id", how="left")


def plan(customers: pd.DataFrame, params: CampaignParams) -> tuple[pd.DataFrame, dict, list[dict]]:
    df = customers.copy()
    charge = df["current_charge"].astype(float).fillna(df["current_charge"].median())
    p = df["churn_probability"].astype(float)
    df["expected_revenue_saved"] = p * params.retention_success_rate * charge * params.months_of_value
    df["expected_value"] = df["expected_revenue_saved"] - params.offer_cost

    eligible = df[df["risk_tier"].isin(params.risk_tiers) & (p >= params.min_probability) & (df["expected_value"] > 0)]
    ranked = eligible.sort_values("expected_value", ascending=False)

    targets = ranked
    if params.max_customers is not None:
        targets = targets.head(int(params.max_customers))
    if params.budget is not None and params.offer_cost > 0:
        targets = targets.head(int(params.budget // params.offer_cost))

    cost = len(targets) * params.offer_cost
    saved = float(targets["expected_revenue_saved"].sum())
    total_expected_churners = float(p.sum())
    summary = {
        "customers_scored": int(len(df)),
        "eligible_customers": int(len(ranked)),
        "targeted_customers": int(len(targets)),
        "campaign_cost": round(cost, 2),
        "expected_revenue_saved": round(saved, 2),
        "expected_profit": round(saved - cost, 2),
        "roi": round((saved - cost) / cost, 3) if cost else None,
        "expected_customers_retained": round(float((targets["churn_probability"] * params.retention_success_rate).sum()), 1),
        "share_of_expected_churners_reached": round(float(targets["churn_probability"].sum()) / total_expected_churners, 4)
        if total_expected_churners else 0.0,
        "average_churn_probability": round(float(targets["churn_probability"].mean()), 4) if len(targets) else None,
    }
    return targets.reset_index(drop=True), summary, profit_curve(ranked, params)


def profit_curve(ranked: pd.DataFrame, params: CampaignParams, points: int = 60) -> list[dict]:
    """Cumulative expected profit when targeting the top-k customers, for the planner chart."""
    if ranked.empty:
        return [{"customers": 0, "expected_profit": 0.0, "cost": 0.0}]
    cumulative = ranked["expected_value"].cumsum().to_numpy()
    ks = np.unique(np.linspace(0, len(ranked), num=min(points, len(ranked) + 1)).astype(int))
    return [{"customers": int(k), "expected_profit": round(float(cumulative[k - 1]) if k else 0.0, 2),
             "cost": round(k * params.offer_cost, 2)} for k in ks]


EXPORT_COLUMNS = ["customer_id", "churn_probability", "risk_tier", "expected_value", "expected_revenue_saved",
                  "current_charge", "region", "plan", "contract_type", "tenure_weeks", "top_reasons"]


def export_frame(targets: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in EXPORT_COLUMNS if c in targets]
    out = targets[cols].copy()
    for col in ("churn_probability", "expected_value", "expected_revenue_saved"):
        if col in out:
            out[col] = out[col].round(4)
    return out
