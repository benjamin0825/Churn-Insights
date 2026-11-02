"""Static matplotlib charts for HTML reports, returned as base64 PNG data URIs.

Styling follows one system: a fixed categorical order keyed by *model name*
(a model keeps its colour in every chart), 2px lines, hairline grids, ink-coloured
text, and reserved status colours that always come with a text label.
"""

from __future__ import annotations

import base64
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.calibration import calibration_curve  # noqa: E402
from sklearn.metrics import precision_recall_curve, roc_curve  # noqa: E402

SURFACE = "#fcfcfb"
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
STATUS = {"stable": "#0ca30c", "warning": "#fab219", "alert": "#d03b3b"}

# Colour follows the entity: fixed slots, never cycled by rank.
MODEL_COLORS = {
    "final model": SERIES[0],
    "logistic_regression": SERIES[1],
    "random_forest": SERIES[2],
    "lightgbm": SERIES[3],
    "xgboost": SERIES[4],
    "tabular_nn": SERIES[5],
}
LABELS = {
    "final model": "Final model (calibrated ensemble)",
    "logistic_regression": "Logistic regression",
    "random_forest": "Random forest",
    "lightgbm": "LightGBM",
    "xgboost": "XGBoost",
    "tabular_nn": "Neural net (PyTorch)",
}

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
        "font.size": 10,
        "text.color": INK,
        "axes.labelcolor": INK_2,
        "axes.edgecolor": AXIS,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.axisbelow": True,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "lines.linewidth": 2,
    }
)


def _to_uri(fig) -> str:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=144, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _ordered(scores: dict[str, np.ndarray]) -> list[str]:
    return sorted(scores, key=lambda n: list(MODEL_COLORS).index(n) if n in MODEL_COLORS else 99)


def roc_chart(y: np.ndarray, scores: dict[str, np.ndarray]) -> str:
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    for name in _ordered(scores):
        fpr, tpr, _ = roc_curve(y, scores[name])
        final = name == "final model"
        ax.plot(
            fpr,
            tpr,
            color=MODEL_COLORS.get(name, MUTED),
            lw=2.6 if final else 1.6,
            label=LABELS.get(name, name),
            zorder=3 if final else 2,
        )
    ax.plot([0, 1], [0, 1], color=AXIS, lw=1, ls="--", label="Random guess")
    ax.set(xlabel="False positive rate", ylabel="True positive rate", xlim=(0, 1), ylim=(0, 1.01))
    ax.set_title("ROC curve, out-of-time test set")
    ax.legend(loc="lower right")
    return _to_uri(fig)


def pr_chart(y: np.ndarray, scores: dict[str, np.ndarray]) -> str:
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    for name in _ordered(scores):
        precision, recall, _ = precision_recall_curve(y, scores[name])
        final = name == "final model"
        ax.plot(
            recall,
            precision,
            color=MODEL_COLORS.get(name, MUTED),
            lw=2.6 if final else 1.6,
            label=LABELS.get(name, name),
            zorder=3 if final else 2,
        )
    ax.axhline(np.mean(y), color=AXIS, lw=1, ls="--", label=f"Base rate ({np.mean(y):.1%})")
    ax.set(xlabel="Recall", ylabel="Precision", xlim=(0, 1), ylim=(0, 1.01))
    ax.set_title("Precision-recall curve, out-of-time test set")
    ax.legend(loc="upper right")
    return _to_uri(fig)


def calibration_chart(y: np.ndarray, raw: np.ndarray, calibrated: np.ndarray) -> str:
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    limit = float(max(np.quantile(raw, 0.995), np.quantile(calibrated, 0.995), 0.05))
    ax.plot([0, limit], [0, limit], color=AXIS, lw=1, ls="--", label="Perfect calibration")
    for label, p, color in (("Blend before calibration", raw, SERIES[1]), ("After calibration", calibrated, SERIES[0])):
        frac, mean = calibration_curve(y, p, n_bins=10, strategy="quantile")
        ax.plot(mean, frac, color=color, marker="o", ms=5, mec=SURFACE, mew=1.5, label=label)
    ax.set(xlabel="Predicted churn probability", ylabel="Observed churn rate", xlim=(0, limit), ylim=(0, None))
    ax.set_title("Calibration, out-of-time test set (10 quantile bins)")
    ax.legend(loc="upper left")
    return _to_uri(fig)


def gains_chart(y: np.ndarray, p: np.ndarray) -> str:
    order = np.argsort(-p)
    captured = np.concatenate([[0], np.cumsum(np.asarray(y)[order]) / max(np.sum(y), 1)])
    share = np.linspace(0, 1, len(captured))
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    ax.plot(share, captured, color=SERIES[0], label="Final model")
    ax.plot([0, 1], [0, 1], color=AXIS, lw=1, ls="--", label="Random targeting")
    at10 = captured[int(round(0.1 * (len(captured) - 1)))]
    ax.scatter([0.1], [at10], s=48, color=SERIES[0], edgecolor=SURFACE, linewidth=2, zorder=4)
    ax.annotate(
        f"Top 10% of customers hold {at10:.0%} of churners",
        (0.1, at10),
        xytext=(14, -4),
        textcoords="offset points",
        color=INK_2,
        fontsize=9,
        va="center",
    )
    ax.set(
        xlabel="Share of customers targeted (highest risk first)",
        ylabel="Share of churners captured",
        xlim=(0, 1),
        ylim=(0, 1.01),
    )
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title("Cumulative gains")
    ax.legend(loc="lower right")
    return _to_uri(fig)


def profit_chart(share: np.ndarray, profit: np.ndarray, chosen_share: float, chosen_profit: float, title: str) -> str:
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    ax.plot(share, profit, color=SERIES[0])
    ax.axhline(0, color=AXIS, lw=1)
    ax.scatter([chosen_share], [chosen_profit], s=56, color=SERIES[0], edgecolor=SURFACE, linewidth=2, zorder=4)
    right = chosen_share > 0.5
    ax.annotate(
        f"Chosen threshold: target {chosen_share:.1%}\nprofit ${chosen_profit:,.0f}",
        (chosen_share, chosen_profit),
        xytext=(-12 if right else 12, -30),
        textcoords="offset points",
        ha="right" if right else "left",
        color=INK_2,
        fontsize=9,
    )
    ax.set(xlabel="Share of customers targeted (highest risk first)", ylabel="Campaign profit ($)")
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_title(title)
    return _to_uri(fig)


def importance_chart(importance: pd.Series, top: int = 15) -> str:
    data = importance.head(top)[::-1]
    fig, ax = plt.subplots(figsize=(6.6, 0.32 * len(data) + 1.2))
    ax.barh([n.replace("_", " ") for n in data.index], data.values, color=SERIES[0], height=0.62)
    ax.grid(axis="y", visible=False)
    ax.set(xlabel="Mean |SHAP value| (log-odds)")
    ax.set_title("What drives churn risk (global SHAP importance)")
    for i, v in enumerate(data.values):
        ax.text(v, i, f" {v:.3f}", va="center", color=INK_2, fontsize=8)
    return _to_uri(fig)


def churn_over_time_chart(rates: pd.Series, split: dict[str, list[int]]) -> str:
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.plot(
        rates.index, rates.values, color=SERIES[0], marker="o", ms=4, mec=SURFACE, mew=1.2, label="8-week churn rate"
    )
    for name, weeks in (("validation", split["validation"]), ("test", split["test"])):
        if weeks:
            ax.axvspan(min(weeks) - 1.5, max(weeks) + 1.5, color=GRID, alpha=0.7, lw=0)
            ax.text(
                (min(weeks) + max(weeks)) / 2, ax.get_ylim()[1], name, ha="center", va="bottom", color=INK_2, fontsize=9
            )
    ax.set(xlabel="Snapshot week", ylabel="Churn rate")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title("Label rate per snapshot (shaded: held-out periods)", pad=16)
    return _to_uri(fig)


def psi_chart(
    table: pd.DataFrame, warning: float, alert: float, top: int = 15, title: str = "Feature drift vs training reference"
) -> str:
    data = table.head(top)[::-1].copy()
    if "segment" in data:
        names = data["feature"].replace({"__prediction__": "model prediction"})
        data["feature"] = data["segment"] + "  " + names
    fig, ax = plt.subplots(figsize=(6.8, 0.32 * len(data) + 1.3))
    colors = [STATUS[s] for s in data["status"]]
    ax.barh([f.replace("_", " ") for f in data["feature"]], data["psi"], color=colors, height=0.62)
    for level, label in ((warning, "warning"), (alert, "alert")):
        ax.axvline(level, color=MUTED, lw=1, ls="--")
        ax.text(level, len(data) - 0.4, f" {label} ({level})", color=INK_2, fontsize=8, va="bottom")
    for i, (v, s) in enumerate(zip(data["psi"], data["status"])):
        ax.text(v, i, f" {v:.3f} {s}", va="center", color=INK_2, fontsize=8)
    ax.grid(axis="y", visible=False)
    ax.set(xlabel="Population stability index (PSI)")
    ax.set_title(title, pad=14)
    return _to_uri(fig)
