"""Single source of truth for engineered feature names and their roles."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..settings import FeaturesConfig

ID_COLUMNS = ["customer_id", "snapshot_week"]
LABEL = "churned"
TEXT_COLUMN = "ticket_text"
VALUE_COLUMN = "current_charge"  # monthly revenue used by the business objective

CATEGORICAL = [
    "region",
    "plan",
    "internet_service",
    "contract_type",
    "payment_method",
    "acquisition_channel",
]

KNOWN_CATEGORIES = {
    "region": ["north", "south", "east", "west"],
    "plan": ["basic", "standard", "premium"],
    "internet_service": ["fiber", "dsl", "none"],
    "contract_type": ["month-to-month", "one-year", "two-year"],
    "payment_method": ["credit-card", "bank-transfer", "electronic-check", "mailed-check"],
    "acquisition_channel": ["online", "retail-store", "partner", "referral"],
}

STATIC_NUMERIC = ["age", "tenure_weeks", "dependents", "has_streaming", "paperless_billing"]
BILLING_NUMERIC = [
    "current_charge",
    "discount_pct",
    "charge_change_12w",
    "late_payments_26w",
    "avg_days_late_26w",
]

# Columns that can never be negative (checked by validation).
NON_NEGATIVE_PREFIXES = ("sessions_", "minutes_", "data_gb_", "tickets_", "late_", "weeks_since")

# "Weeks since X" features are capped so they don't depend on how much history exists.
RECENCY_CAP_WEEKS = 26


@dataclass(frozen=True)
class FeatureSpec:
    windows: tuple[int, ...] = (4, 12)
    numeric: list[str] = field(default_factory=list)
    categorical: list[str] = field(default_factory=lambda: list(CATEGORICAL))
    text: str = TEXT_COLUMN

    @classmethod
    def from_config(cls, cfg: FeaturesConfig) -> FeatureSpec:
        windows = tuple(sorted(set(cfg.windows_weeks)))
        short, long = windows[0], windows[-1]
        usage = []
        for w in windows:
            usage += [f"sessions_mean_{w}w", f"minutes_mean_{w}w", f"data_gb_mean_{w}w", f"tickets_{w}w"]
        usage += [
            f"minutes_std_{long}w",
            f"active_week_ratio_{long}w",
            "weeks_since_active",
            "minutes_trend",
            "sessions_trend",
            f"billing_tickets_{long}w",
            f"technical_tickets_{long}w",
            f"cancellation_tickets_{long}w",
            f"avg_csat_{long}w",
            f"avg_resolution_hours_{long}w",
            "weeks_since_ticket",
        ]
        assert short <= long
        return cls(windows=windows, numeric=STATIC_NUMERIC + BILLING_NUMERIC + usage)

    @property
    def model_inputs(self) -> list[str]:
        return self.numeric + self.categorical + [self.text]

    @property
    def all_columns(self) -> list[str]:
        return ID_COLUMNS + self.model_inputs

    @property
    def short_window(self) -> int:
        return self.windows[0]

    @property
    def long_window(self) -> int:
        return self.windows[-1]
