"""Weekly subscription metrics computed from the raw tables.

MRR is each active customer's latest invoice amount, carried forward between invoices.
A customer counts as active in week ``w`` if they signed up by ``w`` and hadn't churned by
the end of ``w``. Revenue movements come from comparing every invoice with the same
customer's previous one.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd
from churn_ml import kernels

from .workspace import Workspace

MOVEMENT_THRESHOLD = 0.5  # dollars; smaller invoice changes are rounding noise


def start_date(ws: Workspace) -> pd.Timestamp:
    meta = ws.raw_dir / "meta.json"
    value = json.loads(meta.read_text(encoding="utf-8")).get("start_date") if meta.exists() else None
    return pd.Timestamp(value or "2024-01-01")


def weekly(ws: Workspace) -> pd.DataFrame:
    path = ws.raw_dir / "usage.parquet"
    return _weekly(str(ws.raw_dir), path.stat().st_mtime if path.exists() else 0.0, ws.org_id)


PRICE_KEYS = ["plan", "internet_service", "has_streaming"]


def estimated_price(customers: pd.DataFrame, bills: pd.DataFrame) -> pd.Series:
    """Typical first invoice for each customer's plan configuration (aligned to ``customers``)."""
    first = bills.sort_values("week", kind="stable").drop_duplicates("customer_id")[["customer_id", "amount"]]
    priced = customers[["customer_id", *PRICE_KEYS]].merge(first, on="customer_id")
    by_plan = priced.groupby(PRICE_KEYS)["amount"].median().rename("estimate").reset_index()
    estimate = customers[["customer_id", *PRICE_KEYS]].merge(by_plan, on=PRICE_KEYS, how="left")["estimate"]
    return estimate.fillna(first["amount"].median()).set_axis(customers.index)


@lru_cache(maxsize=8)
def _weekly(raw_dir: str, _mtime: float, org_id: int) -> pd.DataFrame:
    raw = Workspace(org_id).raw()
    cust, bills, tickets = raw.customers, raw.billing, raw.tickets
    n_weeks = int(max(raw.usage["week"].max(), bills["week"].max())) + 1
    weeks = np.arange(n_weeks)

    index = pd.Index(cust["customer_id"])
    n = len(index)
    signup = cust["signup_week"].to_numpy()
    churn = cust["churn_week"].to_numpy(dtype=float, na_value=np.inf)

    bills = bills.sort_values(["week", "customer_id"], kind="stable")
    codes = index.get_indexer(bills["customer_id"]).astype(np.int32)
    amounts = bills["amount"].to_numpy(dtype=float)
    bill_weeks = bills["week"].to_numpy()

    # A customer is worth their subscription price from signup on, even before the first invoice
    # arrives (billing runs on a cycle): until then, count them at their first invoice amount.
    first_amount = np.full(n, np.nan)
    first_rows = bills.drop_duplicates("customer_id", keep="first")
    first_amount[index.get_indexer(first_rows["customer_id"])] = first_rows["amount"].to_numpy(dtype=float)
    # Not invoiced at all yet (signed up after the last billing run): estimate from customers on
    # the same plan, internet service and streaming option.
    first_amount = np.where(np.isnan(first_amount), estimated_price(cust, bills).to_numpy(), first_amount)

    mrr, churned_mrr, new_mrr, active, priced = (np.zeros(n_weeks) for _ in range(5))
    for w in weeks:
        hi = int(np.searchsorted(bill_weeks, w, side="right"))
        latest = kernels.group_last(codes[:hi], amounts[:hi], n)[:, 0]
        latest = np.where(np.isnan(latest) & (signup <= w), first_amount, latest)
        is_active = (signup <= w) & (churn > w)
        active[w] = is_active.sum()
        priced[w] = (is_active & ~np.isnan(latest)).sum()
        mrr[w] = np.nansum(latest[is_active])
        churned_mrr[w] = np.nansum(latest[churn == w])
        new_mrr[w] = np.nansum(latest[signup == w])

    # Expansion / contraction: invoice vs the same customer's previous invoice
    by_customer = bills.sort_values(["customer_id", "week"], kind="stable")
    delta = by_customer.groupby("customer_id")["amount"].diff()
    moves = pd.DataFrame({"week": by_customer["week"], "delta": delta}).dropna()
    up = moves[moves["delta"] > MOVEMENT_THRESHOLD].groupby("week")["delta"].agg(["size", "sum"])
    down = moves[moves["delta"] < -MOVEMENT_THRESHOLD].groupby("week")["delta"].agg(["size", "sum"])

    frame = pd.DataFrame({
        "week": weeks,
        "active_customers": active,
        "new_customers": np.bincount(signup[(signup >= 0) & (signup < n_weeks)].astype(int), minlength=n_weeks),
        "churned_customers": np.bincount(churn[np.isfinite(churn)].astype(int), minlength=n_weeks)[:n_weeks],
        "mrr": mrr,
        "new_mrr": new_mrr,
        "churned_mrr": churned_mrr,
        "expansions": up["size"].reindex(weeks, fill_value=0).to_numpy(),
        "expansion_mrr": up["sum"].reindex(weeks, fill_value=0.0).to_numpy(),
        "contractions": down["size"].reindex(weeks, fill_value=0).to_numpy(),
        "contraction_mrr": down["sum"].reindex(weeks, fill_value=0.0).to_numpy(),
        "tickets": np.bincount(tickets["week"].to_numpy().astype(int), minlength=n_weeks)[:n_weeks],
        "cancellation_tickets": np.bincount(
            tickets.loc[tickets["category"] == "cancellation", "week"].to_numpy().astype(int), minlength=n_weeks)[:n_weeks],
        "late_payments": bills.groupby("week")["paid_late"].sum().reindex(weeks, fill_value=0).to_numpy(),
    })
    # 4-week rolling rates (~monthly), the way subscription businesses report churn
    churned_4w = frame["churned_customers"].rolling(4, min_periods=1).sum()
    churned_mrr_4w = frame["churned_mrr"].rolling(4, min_periods=1).sum()
    base_customers = frame["active_customers"].shift(4).bfill()
    base_mrr = frame["mrr"].shift(4).bfill()
    frame["user_churn_rate"] = (churned_4w / base_customers.replace(0, np.nan)).fillna(0.0)
    frame["revenue_churn_rate"] = (churned_mrr_4w / base_mrr.replace(0, np.nan)).fillna(0.0)
    frame["arpu"] = (frame["mrr"] / pd.Series(priced).replace(0, np.nan)).fillna(0.0)  # customers with a known price
    frame["arr"] = frame["mrr"] * 12
    # LTV = ARPU / monthly churn; smooth churn over 12 weeks so one quiet week can't explode it
    smooth_churn = (frame["churned_customers"].rolling(12, min_periods=4).sum() / 3) / frame["active_customers"].replace(0, np.nan)
    frame["ltv"] = (frame["arpu"] / smooth_churn.replace(0, np.nan)).fillna(0.0)
    return frame


# Card definitions: key, label, format, which direction is good
CARDS = [
    ("mrr", "Monthly recurring revenue", "money", "up"),
    ("active_customers", "Active customers", "int", "up"),
    ("user_churn_rate", "User churn (4 wk)", "pct", "down"),
    ("revenue_churn_rate", "Revenue churn (4 wk)", "pct", "down"),
    ("arpu", "Average revenue per customer", "cents", "up"),
    ("ltv", "Customer lifetime value", "money", "up"),
    ("arr", "Annual run rate", "money", "up"),
    ("new_customers", "New customers", "int", "up"),
    ("churned_customers", "Churned customers", "int", "down"),
    ("tickets", "Support tickets", "int", "down"),
    ("cancellation_tickets", "Cancellation requests", "int", "down"),
    ("late_payments", "Late payments", "int", "down"),
]
FLOW_METRICS = {"new_customers", "churned_customers", "tickets", "cancellation_tickets", "late_payments"}


def overview(ws: Workspace, period_weeks: int) -> dict:
    frame = weekly(ws)
    start = start_date(ws)
    last = int(frame["week"].max())
    first = max(0, last - period_weeks + 1)
    window = frame[frame["week"] >= first]
    dates = (start + pd.to_timedelta(window["week"] * 7, unit="D")).dt.strftime("%Y-%m-%d").tolist()
    # Compare against the period just before, of equal length (for flows) or the value at period start
    prev = frame[(frame["week"] >= max(0, first - period_weeks)) & (frame["week"] < first)]

    cards = []
    for key, label, fmt, good in CARDS:
        series = window[key].astype(float)
        if key in FLOW_METRICS:
            value, before = float(series.sum()), float(prev[key].sum()) if len(prev) else None
        else:
            value, before = float(series.iloc[-1]), float(series.iloc[0])
        change = (value - before) / abs(before) if before not in (None, 0) else None
        cards.append({"key": key, "label": label, "format": fmt, "good_when": good, "value": value, "from": before,
                      "change": change, "flow": key in FLOW_METRICS,
                      "series": [{"date": d, "value": round(float(v), 4)} for d, v in zip(dates, series)]})

    recent = frame[frame["week"] > last - 4]
    breakdown = {
        "weeks": 4,
        "new_customers": int(recent["new_customers"].sum()),
        "new_mrr": float(recent["new_mrr"].sum()),
        "expansions": int(recent["expansions"].sum()),
        "expansion_mrr": float(recent["expansion_mrr"].sum()),
        "contractions": int(recent["contractions"].sum()),
        "contraction_mrr": float(recent["contraction_mrr"].sum()),
        "cancellations": int(recent["churned_customers"].sum()),
        "churned_mrr": -float(recent["churned_mrr"].sum()),
    }
    breakdown["net_mrr_change"] = (breakdown["new_mrr"] + breakdown["expansion_mrr"] + breakdown["contraction_mrr"]
                                   + breakdown["churned_mrr"])
    end_date = start + pd.Timedelta(weeks=last + 1)
    return {"as_of": end_date.date().isoformat(), "period": {"weeks": len(window), "start": dates[0], "end": dates[-1]},
            "cards": cards, "breakdown": breakdown, "activity": activity(ws, start, last)}


def activity(ws: Workspace, start: pd.Timestamp, last_week: int, limit: int = 14) -> list[dict]:
    """Recent customer events across the newest weeks, newest first."""
    raw = ws.raw()
    since = last_week - 2
    cust = raw.customers
    by_week = raw.billing.sort_values("week")
    latest_charge = by_week.groupby("customer_id")["amount"].last()
    first_charge = by_week.groupby("customer_id")["amount"].first()
    first_charge = first_charge.combine_first(estimated_price(cust, raw.billing).set_axis(cust["customer_id"]))
    events: list[dict] = []

    def charge(table: pd.Series, customer_id: int) -> float | None:
        value = table.get(customer_id)
        return None if value is None or pd.isna(value) else float(value)

    for row in cust[cust["churn_week"].ge(since).fillna(False)].itertuples():
        amount = charge(latest_charge, row.customer_id)
        events.append({"week": int(row.churn_week), "kind": "cancelled", "customer_id": int(row.customer_id),
                       "amount": None if amount is None else -amount, "detail": f"{row.plan} plan"})
    for row in cust[cust["signup_week"] >= since].itertuples():
        events.append({"week": int(row.signup_week), "kind": "subscribed", "customer_id": int(row.customer_id),
                       "amount": charge(first_charge, row.customer_id), "detail": f"{row.plan} plan"})
    tickets = raw.tickets[(raw.tickets["week"] >= since) & (raw.tickets["category"] == "cancellation")]
    for row in tickets.itertuples():
        events.append({"week": int(row.week), "kind": "cancel_request", "customer_id": int(row.customer_id),
                       "amount": None, "detail": row.text})
    late = raw.billing[(raw.billing["week"] >= since) & raw.billing["paid_late"]]
    for row in late.itertuples():
        events.append({"week": int(row.week), "kind": "paid_late", "customer_id": int(row.customer_id),
                       "amount": float(row.amount), "detail": f"{int(row.days_late)} days late"})

    for e in events:
        e["date"] = (start + pd.Timedelta(weeks=e["week"])).date().isoformat()
        e["weeks_ago"] = last_week - e["week"]
    # Round-robin across event kinds, newest first within each, so the feed shows a mix.
    queues = {kind: sorted((e for e in events if e["kind"] == kind), key=lambda e: -e["week"])
              for kind in ("cancelled", "cancel_request", "subscribed", "paid_late")}
    feed: list[dict] = []
    while len(feed) < limit and any(queues.values()):
        for queue in queues.values():
            if queue and len(feed) < limit:
                feed.append(queue.pop(0))
    return sorted(feed, key=lambda e: e["weeks_ago"])
