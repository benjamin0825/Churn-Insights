"""Model quality and business-value metrics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

from ..settings import BusinessConfig


def expected_calibration_error(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, bins - 1)
    error = 0.0
    for b in range(bins):
        mask = idx == b
        if mask.any():
            error += mask.mean() * abs(y[mask].mean() - p[mask].mean())
    return float(error)


def top_fraction_stats(y: np.ndarray, p: np.ndarray, fraction: float = 0.1) -> tuple[float, float]:
    """(lift, recall) when targeting the highest-scored ``fraction`` of customers."""
    y = np.asarray(y, dtype=float)
    k = max(1, int(round(len(y) * fraction)))
    top = np.argsort(-np.asarray(p))[:k]
    base = y.mean()
    lift = float(y[top].mean() / base) if base > 0 else float("nan")
    recall = float(y[top].sum() / y.sum()) if y.sum() > 0 else float("nan")
    return lift, recall


def ranking_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    lift, recall = top_fraction_stats(y, p, 0.1)
    return {
        "roc_auc": float(roc_auc_score(y, p)),
        "average_precision": float(average_precision_score(y, p)),
        "lift_at_10pct": lift,
        "recall_at_10pct": recall,
    }


def probability_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    clipped = np.clip(p, 1e-6, 1 - 1e-6)
    return {
        "brier": float(brier_score_loss(y, clipped)),
        "log_loss": float(log_loss(y, clipped, labels=[0, 1])),
        "ece": expected_calibration_error(y, clipped),
    }


def decision_metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> dict[str, float]:
    pred = (np.asarray(p) >= threshold).astype(int)
    return {
        "threshold": float(threshold),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "targeted_share": float(pred.mean()),
    }


@dataclass
class ProfitCurve:
    thresholds: np.ndarray  # score of the k-th customer when targeting the top k
    targeted_share: np.ndarray
    profit: np.ndarray

    @property
    def best_index(self) -> int:
        return int(np.argmax(self.profit))

    @property
    def best_threshold(self) -> float:
        return float(self.thresholds[self.best_index])

    @property
    def best_profit(self) -> float:
        return float(self.profit[self.best_index])


def profit_curve(y: np.ndarray, p: np.ndarray, monthly_value: np.ndarray, business: BusinessConfig) -> ProfitCurve:
    """Campaign profit when targeting the top-k customers for every k.

    A targeted true churner is saved with probability ``retention_success_rate``
    and is worth ``monthly_value * months_of_value``; every offer costs ``offer_cost``.
    """
    order = np.argsort(-np.asarray(p, dtype=float), kind="stable")
    y_sorted = np.asarray(y, dtype=float)[order]
    value = np.nan_to_num(np.asarray(monthly_value, dtype=float)[order], nan=np.nanmedian(monthly_value))
    gain = y_sorted * business.retention_success_rate * value * business.months_of_value - business.offer_cost
    profit = np.concatenate([[0.0], np.cumsum(gain)])
    thresholds = np.concatenate([[1.0 + 1e-9], np.asarray(p, dtype=float)[order]])
    share = np.arange(len(profit)) / len(y_sorted)
    return ProfitCurve(thresholds, share, profit)


def business_metrics(y, p, monthly_value, threshold: float, business: BusinessConfig) -> dict[str, float]:
    y = np.asarray(y, dtype=float)
    value = np.nan_to_num(np.asarray(monthly_value, dtype=float), nan=np.nanmedian(monthly_value))
    targeted = np.asarray(p) >= threshold
    per_customer = y * business.retention_success_rate * value * business.months_of_value - business.offer_cost
    return {
        "campaign_profit": float(per_customer[targeted].sum()),
        "profit_if_target_all": float(per_customer.sum()),
        "customers_targeted": int(targeted.sum()),
        "churners_reached": int(y[targeted].sum()),
        "revenue_saved": float(
            (y * business.retention_success_rate * value * business.months_of_value)[targeted].sum()
        ),
        "campaign_cost": float(targeted.sum() * business.offer_cost),
    }


def full_report(y, p, monthly_value, threshold: float, business: BusinessConfig) -> dict[str, float]:
    return {
        **ranking_metrics(y, p),
        **probability_metrics(y, p),
        **decision_metrics(y, p, threshold),
        **business_metrics(y, p, monthly_value, threshold, business),
        "positive_rate": float(np.mean(y)),
        "rows": int(len(y)),
    }


def score_for_tuning(metric: str, y, p) -> float:
    return float(average_precision_score(y, p) if metric == "average_precision" else roc_auc_score(y, p))
