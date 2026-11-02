"""Data-quality gates for raw tables and engineered feature frames."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..features.spec import KNOWN_CATEGORIES, LABEL, NON_NEGATIVE_PREFIXES, FeatureSpec
from .simulator import SimulatedData


class DataValidationError(ValueError):
    def __init__(self, report: ValidationReport):
        super().__init__("; ".join(report.errors))
        self.report = report


@dataclass
class ValidationReport:
    name: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, float] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def check(self, condition: bool, message: str, *, warning: bool = False) -> None:
        if not condition:
            (self.warnings if warning else self.errors).append(message)

    def raise_for_errors(self) -> ValidationReport:
        if self.errors:
            raise DataValidationError(self)
        return self

    def to_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "errors": self.errors, "warnings": self.warnings, "stats": self.stats}


def validate_raw(data: SimulatedData) -> ValidationReport:
    report = ValidationReport("raw_tables")
    cust, usage, bills, tickets = data.customers, data.usage, data.billing, data.tickets

    report.check(cust["customer_id"].is_unique, "customers.customer_id is not unique")
    known = set(cust["customer_id"])
    for name, table in (("usage", usage), ("billing", bills), ("tickets", tickets)):
        orphans = ~table["customer_id"].isin(known)
        report.check(not orphans.any(), f"{name}: {int(orphans.sum())} rows reference unknown customers")

    churn = cust.set_index("customer_id")["churn_week"]
    for name, table in (("usage", usage), ("billing", bills), ("tickets", tickets)):
        cw = churn.reindex(table["customer_id"]).to_numpy(dtype=float, na_value=np.inf)
        after = table["week"].to_numpy() > cw
        report.check(not after.any(), f"{name}: {int(after.sum())} events after the customer churned")

    report.check((usage[["sessions", "minutes", "data_gb"]] >= 0).all().all(), "usage has negative values")
    report.check((bills["amount"] > 0).all(), "billing has non-positive invoice amounts")
    report.check(tickets["csat"].between(1, 5).all(), "tickets.csat outside 1..5")
    report.check(tickets["text"].str.len().gt(0).all(), "tickets with empty text")

    for col, allowed in KNOWN_CATEGORIES.items():
        if col in cust:
            unknown = set(cust[col].dropna()) - set(allowed)
            report.check(not unknown, f"customers.{col} has unknown values {sorted(unknown)}")

    for col in ("age", "payment_method"):
        rate = float(cust[col].isna().mean())
        report.stats[f"null_rate.{col}"] = round(rate, 4)
        report.check(rate < 0.10, f"customers.{col} null rate {rate:.1%} exceeds 10%", warning=True)

    report.stats.update({k: float(v) for k, v in data.summary().items()})
    return report


def validate_features(
    df: pd.DataFrame, spec: FeatureSpec, *, require_label: bool = False, max_null_rate: float = 0.5
) -> ValidationReport:
    report = ValidationReport("features")
    missing = [c for c in spec.model_inputs if c not in df.columns]
    report.check(not missing, f"missing feature columns: {missing}")
    if missing:
        return report
    report.check(len(df) > 0, "feature frame is empty")

    for col in spec.numeric:
        if not pd.api.types.is_numeric_dtype(df[col]):
            report.errors.append(f"{col} must be numeric, got {df[col].dtype}")
            continue
        values = df[col].to_numpy(dtype=float)
        if np.isinf(values).any():
            report.errors.append(f"{col} contains infinite values")
        if col.startswith(NON_NEGATIVE_PREFIXES) and (values[~np.isnan(values)] < 0).any():
            report.errors.append(f"{col} contains negative values")
        null_rate = float(np.isnan(values).mean()) if len(values) else 0.0
        if null_rate > max_null_rate:
            report.warnings.append(f"{col} null rate {null_rate:.1%}")

    for col in spec.categorical:
        unknown = set(df[col].dropna().astype(str)) - set(KNOWN_CATEGORIES.get(col, []))
        report.check(not unknown, f"{col} has unseen categories {sorted(unknown)[:5]}", warning=True)

    report.check(df[spec.text].map(lambda v: isinstance(v, str)).all(), f"{spec.text} must be strings")

    if require_label:
        report.check(LABEL in df.columns, f"label column {LABEL!r} missing")
        if LABEL in df.columns:
            labels = df[LABEL]
            report.check(labels.notna().all(), "label has missing values")
            report.check(set(labels.dropna().unique()) <= {0, 1}, "label must be binary 0/1")
            report.stats["positive_rate"] = round(float(labels.mean()), 4)
    report.stats["rows"] = float(len(df))
    return report
