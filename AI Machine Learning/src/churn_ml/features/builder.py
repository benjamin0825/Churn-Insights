"""Point-in-time feature engineering.

For a snapshot week ``S`` the builder:

* selects customers who signed up before ``S`` and had not churned before ``S``,
* aggregates **only events with week < S** (usage, invoices, tickets),
* labels the row 1 when the customer churns in ``[S, S + horizon)``.

Because all inputs are cut at ``S``, appending future data never changes a
snapshot's features. ``tests/test_features.py`` checks this property.

Aggregations run through ``churn_ml.kernels``: single-pass group-by kernels over
week-sorted event arrays, compiled in ``_native`` (Cython) with a NumPy fallback.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import kernels
from ..data.simulator import SimulatedData
from ..logging_utils import get_logger
from ..settings import FeaturesConfig
from .spec import LABEL, RECENCY_CAP_WEEKS, FeatureSpec

log = get_logger(__name__)

TICKET_CATEGORIES = ("billing", "technical", "cancellation")


class _Events:
    """One event table as week-sorted NumPy columns plus dense customer codes."""

    def __init__(self, table: pd.DataFrame, customer_index: pd.Index, columns: list[str]):
        table = table.sort_values("week", kind="stable").reset_index(drop=True)
        self.week = table["week"].to_numpy(dtype=np.int64)
        self.codes = customer_index.get_indexer(table["customer_id"]).astype(np.int32)
        self.columns = {c: table[c].to_numpy() for c in columns}

    def start(self, week: int) -> int:
        """Index of the first row with week >= ``week``."""
        return int(np.searchsorted(self.week, week, side="left"))

    def matrix(self, names: list[str], lo: int, hi: int) -> np.ndarray:
        return np.column_stack([self.columns[n][lo:hi].astype(np.float64) for n in names])


class FeatureBuilder:
    def __init__(self, data: SimulatedData, cfg: FeaturesConfig, horizon_weeks: int):
        self.cfg = cfg
        self.spec = FeatureSpec.from_config(cfg)
        self.horizon = horizon_weeks
        self.customers = data.customers.reset_index(drop=True)
        index = pd.Index(self.customers["customer_id"])
        self.n_customers = len(index)
        self.usage = _Events(data.usage, index, ["sessions", "minutes", "data_gb"])
        self.billing = _Events(data.billing, index, ["amount", "discount_pct", "paid_late", "days_late"])
        self.tickets = _Events(data.tickets, index, ["category", "text", "resolution_hours", "csat"])
        lookup = {c: i for i, c in enumerate(TICKET_CATEGORIES)}
        self._ticket_cat = np.array([lookup.get(c, -1) for c in self.tickets.columns["category"]], dtype=np.int32)
        self._signup = self.customers["signup_week"].to_numpy()
        self._churn = self.customers["churn_week"].to_numpy(dtype=float, na_value=np.inf)
        self.n_weeks = int(max(self.usage.week.max(), self.billing.week.max(), self.tickets.week.max())) + 1

    # ------------------------------------------------------------------ API
    def build_snapshot(self, week: int) -> pd.DataFrame:
        pos = np.flatnonzero((self._signup < week) & (self._churn >= week))
        base = self.customers.iloc[pos]
        frame = pd.DataFrame(index=pd.RangeIndex(len(pos)))
        frame["customer_id"] = base["customer_id"].to_numpy(dtype=np.int32)
        frame["snapshot_week"] = np.int16(week)

        self._static(frame, base, week)
        self._usage(frame, pos, week)
        self._billing(frame, pos, week)
        self._tickets(frame, pos, week)

        if week + self.horizon <= self.n_weeks:
            churn = self._churn[pos]
            frame[LABEL] = ((churn >= week) & (churn < week + self.horizon)).astype(np.int8)
        else:
            frame[LABEL] = np.nan  # label window extends past the data: scoring-only snapshot

        float_cols = [c for c in self.spec.numeric if c in frame]
        frame[float_cols] = frame[float_cols].astype(np.float32)
        return frame

    def build_many(self, weeks: list[int]) -> pd.DataFrame:
        frames = []
        for w in weeks:
            frames.append(self.build_snapshot(w))
            log.debug("snapshot %s: %s rows", w, len(frames[-1]))
        return pd.concat(frames, ignore_index=True)

    # -------------------------------------------------------------- pieces
    def _static(self, frame: pd.DataFrame, base: pd.DataFrame, week: int) -> None:
        frame["age"] = base["age"].to_numpy(dtype=float)
        frame["tenure_weeks"] = (week - base["signup_week"]).to_numpy(dtype=float)
        frame["dependents"] = base["dependents"].to_numpy(dtype=float)
        frame["has_streaming"] = base["has_streaming"].to_numpy(dtype=float)
        frame["paperless_billing"] = base["paperless_billing"].to_numpy(dtype=float)
        for col in self.spec.categorical:
            frame[col] = base[col].to_numpy()

    @staticmethod
    def _recency(frame: pd.DataFrame, last_week: np.ndarray, week: int) -> pd.Series:
        """Weeks since the last event; customers with none count their whole tenure."""
        since = pd.Series(week - last_week, index=frame.index)
        return since.fillna(frame["tenure_weeks"]).clip(upper=RECENCY_CAP_WEEKS)

    def _usage(self, frame: pd.DataFrame, pos: np.ndarray, week: int) -> None:
        spec, ev, n = self.spec, self.usage, self.n_customers
        long, short = spec.long_window, spec.short_window
        cols = ["sessions", "minutes", "data_gb"]
        hi = ev.start(week)
        for w in spec.windows:
            lo = ev.start(week - w)
            mean, std, _ = kernels.group_mean_std(ev.codes[lo:hi], ev.matrix(cols, lo, hi), n)
            for j, col in enumerate(cols):
                frame[f"{col}_mean_{w}w"] = mean[pos, j]
            if w == long:
                frame[f"minutes_std_{long}w"] = std[pos, 1]
                active = (ev.columns["sessions"][lo:hi] > 0).astype(np.float64)
                ratio, _, _ = kernels.group_mean_std(ev.codes[lo:hi], active, n)
                frame[f"active_week_ratio_{long}w"] = ratio[pos, 0]

        last_active = kernels.group_max_where(ev.codes[:hi], ev.week[:hi], ev.columns["sessions"][:hi] > 0, n)
        frame["weeks_since_active"] = self._recency(frame, last_active[pos], week)
        frame["minutes_trend"] = frame[f"minutes_mean_{short}w"] / (frame[f"minutes_mean_{long}w"] + 1.0)
        frame["sessions_trend"] = frame[f"sessions_mean_{short}w"] / (frame[f"sessions_mean_{long}w"] + 0.5)

    def _billing(self, frame: pd.DataFrame, pos: np.ndarray, week: int) -> None:
        ev, n = self.billing, self.n_customers
        hi = ev.start(week)
        latest = kernels.group_last(ev.codes[:hi], ev.matrix(["amount", "discount_pct"], 0, hi), n)
        frame["current_charge"] = latest[pos, 0]
        frame["discount_pct"] = np.nan_to_num(latest[pos, 1], nan=0.0)

        hi_old = ev.start(week - 11)  # invoices with week <= S - 12
        older = kernels.group_last(ev.codes[:hi_old], ev.matrix(["amount"], 0, hi_old), n)
        frame["charge_change_12w"] = frame["current_charge"] / older[pos, 0]

        lo = ev.start(week - 26)
        sums, _, counts = kernels.group_stats(ev.codes[lo:hi], ev.matrix(["paid_late", "days_late"], lo, hi), n)
        frame["late_payments_26w"] = sums[pos, 0]
        with np.errstate(invalid="ignore", divide="ignore"):
            frame["avg_days_late_26w"] = np.nan_to_num(sums[pos, 1] / counts[pos], nan=0.0)

    def _tickets(self, frame: pd.DataFrame, pos: np.ndarray, week: int) -> None:
        spec, ev, n = self.spec, self.tickets, self.n_customers
        long = spec.long_window
        hi = ev.start(week)
        for w in spec.windows:
            codes = ev.codes[ev.start(week - w) : hi]
            frame[f"tickets_{w}w"] = np.bincount(codes[codes >= 0], minlength=n)[pos].astype(float)

        lo = ev.start(week - long)
        by_cat = kernels.group_category_counts(ev.codes[lo:hi], self._ticket_cat[lo:hi], n, len(TICKET_CATEGORIES))
        for j, cat in enumerate(TICKET_CATEGORIES):
            frame[f"{cat}_tickets_{long}w"] = by_cat[pos, j].astype(float)

        mean, _, _ = kernels.group_mean_std(ev.codes[lo:hi], ev.matrix(["csat", "resolution_hours"], lo, hi), n)
        frame[f"avg_csat_{long}w"] = mean[pos, 0]
        frame[f"avg_resolution_hours_{long}w"] = mean[pos, 1]

        last = kernels.group_max_where(ev.codes[:hi], ev.week[:hi], np.ones(hi, dtype=bool), n)
        frame["weeks_since_ticket"] = self._recency(frame, last[pos], week)

        lo_text = ev.start(week - self.cfg.text_window_weeks)
        texts = kernels.group_join(ev.codes[lo_text:hi], ev.columns["text"][lo_text:hi], n)
        frame[spec.text] = texts[pos]
