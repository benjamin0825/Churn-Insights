"""SHAP explanations mapped back to human-readable input features.

The explainer runs ``shap.TreeExplainer`` on the ensemble's strongest tree
member. Contributions of one-hot columns and text-embedding components are
summed back to their source feature, so a reason reads "contract_type" or
"ticket_text" instead of "cat__contract_type_month-to-month".
"""

from __future__ import annotations

import warnings
from functools import cached_property

import numpy as np
import pandas as pd

from ..models.churn_model import ChurnModel
from ..models.preprocessing import source_feature

READABLE = {
    "tenure_weeks": "time as a customer",
    "contract_type": "contract type",
    "payment_method": "payment method",
    "ticket_text": "wording of recent support tickets",
    "current_charge": "current monthly charge",
    "charge_change_12w": "price change over the last 12 weeks",
    "discount_pct": "active discount",
    "weeks_since_ticket": "time since last support ticket",
}


class ExplainerUnavailable(RuntimeError):
    pass


class ShapExplainer:
    def __init__(self, model: ChurnModel):
        if not model.explainer_model:
            raise ExplainerUnavailable("model bundle has no tree-based member to explain")
        self.model = model
        pipeline = model.pipelines[model.explainer_model]
        self.preprocess, self.estimator = pipeline[:-1], pipeline[-1]
        names = self.preprocess.get_feature_names_out()
        self.sources = np.array([source_feature(n, model.spec) for n in names])
        self.source_names = list(dict.fromkeys(self.sources))

    @cached_property
    def _explainer(self):
        import shap

        return shap.TreeExplainer(self.estimator)

    def contributions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Per-row SHAP values (log-odds) aggregated to source features."""
        X = self.preprocess.transform(self.model.prepare(df))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # LightGBM output-format notice
            values = self._explainer.shap_values(X, check_additivity=False)
        if isinstance(values, list):
            values = values[1]
        values = np.asarray(values)
        if values.ndim == 3:
            values = values[:, :, 1]
        grouped = pd.DataFrame(values, columns=self.sources).T.groupby(level=0, sort=False).sum().T
        return grouped[self.source_names].set_axis(df.index)

    def global_importance(self, df: pd.DataFrame) -> pd.Series:
        return self.contributions(df).abs().mean().sort_values(ascending=False)

    def reasons(self, df: pd.DataFrame, top_n: int = 5) -> list[list[dict]]:
        contrib = self.contributions(df)
        result = []
        for idx, row in contrib.iterrows():
            top = row.reindex(row.abs().sort_values(ascending=False).index)[:top_n]
            items = []
            for feature, value in top.items():
                raw = df.at[idx, feature] if feature in df else None
                if isinstance(raw, str) and len(raw) > 80:
                    raw = raw[:77] + "..."
                if isinstance(raw, (np.floating, float)):
                    raw = None if np.isnan(raw) else round(float(raw), 3)
                elif isinstance(raw, np.integer):
                    raw = int(raw)
                items.append(
                    {
                        "feature": feature,
                        "description": READABLE.get(feature, feature.replace("_", " ")),
                        "value": raw,
                        "impact": round(float(value), 4),
                        "direction": "increases risk" if value > 0 else "decreases risk",
                    }
                )
            result.append(items)
        return result


def try_explainer(model: ChurnModel) -> ShapExplainer | None:
    try:
        return ShapExplainer(model)
    except ExplainerUnavailable:
        return None
