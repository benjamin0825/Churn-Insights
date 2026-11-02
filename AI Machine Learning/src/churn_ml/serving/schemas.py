"""Request/response models. The feature record schema is generated from the FeatureSpec."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from ..features.spec import KNOWN_CATEGORIES, FeatureSpec


def feature_record_model(spec: FeatureSpec) -> type[BaseModel]:
    fields: dict[str, Any] = {
        "customer_id": (int | None, None),
        "snapshot_week": (int | None, None),
    }
    for col in spec.numeric:
        fields[col] = (float | None, Field(None, description="numeric feature; null is imputed"))
    for col in spec.categorical:
        fields[col] = (str | None, Field(None, description=f"one of {KNOWN_CATEGORIES.get(col)}"))
    fields[spec.text] = (str, Field("", description="recent support ticket text"))
    return create_model("FeatureRecord", __config__=ConfigDict(extra="forbid"), **fields)


class Reason(BaseModel):
    feature: str
    description: str
    value: Any = None
    impact: float
    direction: Literal["increases risk", "decreases risk"]


class Prediction(BaseModel):
    customer_id: int | None = None
    churn_probability: float
    risk_tier: Literal["low", "medium", "high"]
    target_for_retention: bool
    expected_revenue_at_risk: float | None = None
    reasons: list[Reason] | None = None


class PredictionResponse(BaseModel):
    model_version: int
    threshold: float
    predictions: list[Prediction]


class CustomerScoreRequest(BaseModel):
    customer_ids: list[int] = Field(min_length=1, max_length=5000)
    as_of_week: int | None = Field(None, description="defaults to the end of the stored history")
    explain: bool = False


class CustomerScoreResponse(PredictionResponse):
    as_of_week: int
    not_found: list[int]


class DriftFeature(BaseModel):
    feature: str
    kind: str
    psi: float
    ks_pvalue: float | None = None
    status: str


class DriftResponse(BaseModel):
    model_version: int
    status: str
    n_reference: int
    n_current: int
    prediction: dict[str, Any] | None
    features: list[DriftFeature]


class ModelInfo(BaseModel):
    version: int
    description: dict[str, Any]
    test_metrics: dict[str, Any]
    features: dict[str, list[str] | str]
