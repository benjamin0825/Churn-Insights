"""CSV ingestion: four uploaded tables -> the ``churn_ml`` raw-table format.

Uploads use calendar dates (``signup_date``, ``week_start``, ``invoice_date``, ``created_at``);
integer ``week`` columns are accepted too. Everything is mapped onto one weekly timeline
whose week 0 is the Monday of the first usage week.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from churn_ml.data.simulator import SimulatedData
from churn_ml.data.validation import validate_raw

TRUE = {"true", "1", "yes", "y", "t"}
FALSE = {"false", "0", "no", "n", "f", ""}

SCHEMAS: dict[str, dict[str, str]] = {
    "customers": {
        "customer_id": "int", "signup_date": "date", "age": "float?", "region": "str", "plan": "str",
        "internet_service": "str", "has_streaming": "bool", "contract_type": "str", "payment_method": "str?",
        "paperless_billing": "bool", "dependents": "int", "acquisition_channel": "str", "churn_date": "date?",
    },
    "usage": {"customer_id": "int", "week_start": "date", "sessions": "int", "minutes": "float", "data_gb": "float"},
    "billing": {
        "customer_id": "int", "invoice_date": "date", "amount": "float", "discount_pct": "float",
        "paid_late": "bool", "days_late": "int",
    },
    "tickets": {
        "customer_id": "int", "created_at": "date", "category": "str", "text": "str",
        "resolution_hours": "float", "csat": "int",
    },
}
DATE_TO_WEEK = {"signup_date": "signup_week", "week_start": "week", "invoice_date": "week",
                "created_at": "week", "churn_date": "churn_week"}
TABLES = tuple(SCHEMAS)


class IngestError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass
class IngestResult:
    data: SimulatedData
    start_date: pd.Timestamp
    n_weeks: int
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {**self.data.summary(), "n_weeks": self.n_weeks, "start_date": self.start_date.date().isoformat(),
                "end_date": (self.start_date + pd.Timedelta(weeks=self.n_weeks)).date().isoformat()}


def _read(name: str, raw: bytes) -> pd.DataFrame:
    try:
        frame = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except Exception as exc:  # malformed CSV
        raise IngestError([f"{name}.csv could not be parsed: {exc}"]) from None
    frame.columns = [c.strip().lower() for c in frame.columns]
    return frame


def _coerce(name: str, frame: pd.DataFrame, errors: list[str]) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    for col, kind in SCHEMAS[name].items():
        optional = kind.endswith("?")
        kind = kind.rstrip("?")
        week_col = DATE_TO_WEEK.get(col)
        if col not in frame and week_col and week_col in frame:  # integer week supplied instead of a date
            out[week_col] = pd.to_numeric(frame[week_col], errors="coerce")
            continue
        if col not in frame:
            if optional:
                out[col] = np.nan if kind != "str" else None
                continue
            errors.append(f"{name}.csv: missing column '{col}'")
            continue
        values = frame[col].str.strip()
        blank = values.eq("")
        if kind == "date":
            parsed = pd.to_datetime(values.where(~blank), errors="coerce", utc=True).dt.tz_localize(None)
            bad = parsed.isna() & ~blank
            out[col] = parsed
        elif kind in ("int", "float"):
            parsed = pd.to_numeric(values.where(~blank), errors="coerce")
            bad = parsed.isna() & ~blank
            out[col] = parsed
        elif kind == "bool":
            lowered = values.str.lower()
            bad = ~lowered.isin(TRUE | FALSE)
            out[col] = lowered.isin(TRUE)
        else:
            bad = pd.Series(False, index=frame.index)
            out[col] = values.where(~blank, None)
        missing = blank & (not optional) & (kind != "bool")
        if bad.any():
            errors.append(f"{name}.csv: {int(bad.sum())} rows have an invalid {kind} in '{col}' "
                          f"(first at row {int(bad.idxmax()) + 2})")
        if missing.any():
            errors.append(f"{name}.csv: {int(missing.sum())} rows have an empty '{col}'")
    return out


def _monday(ts: pd.Timestamp) -> pd.Timestamp:
    return (ts - pd.Timedelta(days=ts.weekday())).normalize()


def ingest_csv(files: dict[str, bytes], min_history_weeks: int = 52) -> IngestResult:
    missing = [t for t in TABLES if t not in files]
    if missing:
        raise IngestError([f"missing file: {t}.csv" for t in missing])
    errors: list[str] = []
    tables = {name: _coerce(name, _read(name, files[name]), errors) for name in TABLES}
    if errors:
        raise IngestError(errors)

    usage_dates = tables["usage"].get("week_start")
    if usage_dates is not None:
        start = _monday(usage_dates.min())
    else:
        start = pd.Timestamp("2000-01-03")  # integer weeks throughout: dates are only cosmetic

    def to_week(series: pd.Series) -> pd.Series:
        if pd.api.types.is_datetime64_any_dtype(series):
            return np.floor((series - start).dt.days / 7)
        return series

    for frame in tables.values():
        for date_col, week_col in DATE_TO_WEEK.items():
            if date_col in frame:
                frame[week_col] = to_week(frame.pop(date_col))

    c = tables["customers"]
    customers = pd.DataFrame({
        "customer_id": c["customer_id"].astype(np.int32),
        "signup_week": c["signup_week"].astype(np.int32),
        "signup_date": start + pd.to_timedelta(c["signup_week"] * 7, unit="D"),
        "age": c["age"].astype(float),
        "region": c["region"], "plan": c["plan"], "internet_service": c["internet_service"],
        "has_streaming": c["has_streaming"].astype(bool), "contract_type": c["contract_type"],
        "payment_method": c["payment_method"], "paperless_billing": c["paperless_billing"].astype(bool),
        "dependents": c["dependents"].astype(np.int16), "acquisition_channel": c["acquisition_channel"],
        "churn_week": pd.array(c["churn_week"], dtype="Int32"),
    })
    customers["churn_date"] = start + pd.to_timedelta(customers["churn_week"].astype(float) * 7, unit="D")

    u, b, t = tables["usage"], tables["billing"], tables["tickets"]
    usage = pd.DataFrame({"customer_id": u["customer_id"].astype(np.int32), "week": u["week"].astype(np.int16),
                          "sessions": u["sessions"].astype(np.int16), "minutes": u["minutes"].astype(np.float32),
                          "data_gb": u["data_gb"].astype(np.float32)})
    billing = pd.DataFrame({"customer_id": b["customer_id"].astype(np.int32), "week": b["week"].astype(np.int16),
                            "amount": b["amount"].astype(np.float32), "discount_pct": b["discount_pct"].astype(np.float32),
                            "paid_late": b["paid_late"].astype(bool), "days_late": b["days_late"].astype(np.int16)})
    billing["invoice_date"] = start + pd.to_timedelta(billing["week"].astype(int) * 7, unit="D")
    tickets = pd.DataFrame({"customer_id": t["customer_id"].astype(np.int32), "week": t["week"].astype(np.int16),
                            "category": t["category"], "text": t["text"].fillna(""),
                            "resolution_hours": t["resolution_hours"].astype(np.float32),
                            "csat": t["csat"].astype(np.int8)})
    tickets.insert(0, "ticket_id", np.arange(len(tickets), dtype=np.int32))
    tickets["created_at"] = start + pd.to_timedelta(tickets["week"].astype(int) * 7, unit="D")

    data = SimulatedData(customers, usage, billing, tickets)
    last_ticket_week = tickets["week"].max() if len(tickets) else 0
    n_weeks = int(max(usage["week"].max(), billing["week"].max(), last_ticket_week)) + 1
    report = validate_raw(data)
    problems = list(report.errors)
    if n_weeks < min_history_weeks:
        problems.append(f"only {n_weeks} weeks of history; at least {min_history_weeks} are needed to train")
    if (usage["week"] < 0).any():
        problems.append("usage rows dated before the first usage week")
    if problems:
        raise IngestError(problems)
    return IngestResult(data, start, n_weeks, report.warnings)


def to_csv_tables(data: SimulatedData, start: pd.Timestamp, limit_customers: int | None = None) -> dict[str, str]:
    """Inverse of ingest_csv: raw tables -> upload-format CSV text (used for templates/samples)."""
    customers = data.customers
    if limit_customers:
        keep = set(customers["customer_id"].head(limit_customers))
        customers = customers[customers["customer_id"].isin(keep)]
        pick = lambda f: f[f["customer_id"].isin(keep)]  # noqa: E731
    else:
        pick = lambda f: f  # noqa: E731

    def date(week) -> pd.Series:
        return (start + pd.to_timedelta(pd.Series(week).astype(float) * 7, unit="D")).dt.date

    c = customers.copy()
    cust = pd.DataFrame({
        "customer_id": c["customer_id"], "signup_date": date(c["signup_week"]).values, "age": c["age"],
        "region": c["region"], "plan": c["plan"], "internet_service": c["internet_service"],
        "has_streaming": c["has_streaming"], "contract_type": c["contract_type"],
        "payment_method": c["payment_method"], "paperless_billing": c["paperless_billing"],
        "dependents": c["dependents"], "acquisition_channel": c["acquisition_channel"],
        "churn_date": date(c["churn_week"]).values,
    })
    u, b, t = pick(data.usage), pick(data.billing), pick(data.tickets)
    usage = pd.DataFrame({"customer_id": u["customer_id"], "week_start": date(u["week"]).values,
                          "sessions": u["sessions"], "minutes": u["minutes"].round(1), "data_gb": u["data_gb"].round(3)})
    billing = pd.DataFrame({"customer_id": b["customer_id"], "invoice_date": date(b["week"]).values,
                            "amount": b["amount"].round(2), "discount_pct": b["discount_pct"],
                            "paid_late": b["paid_late"], "days_late": b["days_late"]})
    tickets = pd.DataFrame({"customer_id": t["customer_id"], "created_at": date(t["week"]).values,
                            "category": t["category"], "text": t["text"],
                            "resolution_hours": t["resolution_hours"], "csat": t["csat"]})
    return {name: frame.to_csv(index=False) for name, frame in
            (("customers", cust), ("usage", usage), ("billing", billing), ("tickets", tickets))}
