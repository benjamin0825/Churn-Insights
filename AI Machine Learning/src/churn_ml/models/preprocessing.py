"""Feature preprocessing: numeric hygiene, categorical encoding and ticket-text embeddings."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, OrdinalEncoder, StandardScaler
from sklearn.utils.validation import check_is_fitted

from ..features.spec import FeatureSpec
from ..settings import FeaturesConfig

Encoding = Literal["onehot", "ordinal"]


class Winsorizer(TransformerMixin, BaseEstimator):
    """Clip each numeric column to quantiles learned at fit time (NaNs pass through)."""

    def __init__(self, lower: float = 0.005, upper: float = 0.995):
        self.lower = lower
        self.upper = upper

    def fit(self, X, y=None):
        values = np.asarray(X, dtype=float)
        self.n_features_in_ = values.shape[1]
        if hasattr(X, "columns"):
            self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        self.lower_ = np.nanquantile(values, self.lower, axis=0)
        self.upper_ = np.nanquantile(values, self.upper, axis=0)
        return self

    def transform(self, X):
        check_is_fitted(self, "lower_")
        return np.clip(np.asarray(X, dtype=float), self.lower_, self.upper_)

    def get_feature_names_out(self, input_features=None):
        if input_features is not None:
            return np.asarray(input_features, dtype=object)
        if hasattr(self, "feature_names_in_"):
            return self.feature_names_in_
        return np.asarray([f"x{i}" for i in range(self.n_features_in_)], dtype=object)


def clean_categories(X):
    """Missing -> 'missing'; everything as str so encoders see one consistent dtype."""
    frame = pd.DataFrame(X).astype(object)
    return frame.where(frame.notna(), "missing").astype(str)


def fill_text(X):
    series = pd.Series(np.asarray(X, dtype=object).ravel())
    return series.where(series.notna(), "").astype(str)


def build_preprocessor(
    spec: FeatureSpec, cfg: FeaturesConfig, encoding: Encoding = "onehot", seed: int = 42
) -> ColumnTransformer:
    numeric = Pipeline(
        [
            ("winsorize", Winsorizer()),
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]
    )
    text = Pipeline(
        [
            ("fill", FunctionTransformer(fill_text, feature_names_out="one-to-one")),
            (
                "tfidf",
                TfidfVectorizer(max_features=cfg.tfidf_max_features, ngram_range=(1, 2), min_df=5, sublinear_tf=True),
            ),
            ("svd", TruncatedSVD(n_components=cfg.svd_components, random_state=seed)),
        ]
    )
    if encoding == "onehot":
        encoder = OneHotEncoder(handle_unknown="ignore", min_frequency=0.005, sparse_output=False)
    else:
        encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    categorical = Pipeline(
        [
            ("clean", FunctionTransformer(clean_categories, feature_names_out="one-to-one")),
            ("encode", encoder),
        ]
    )
    # Categorical columns go last: the neural net reads them as the trailing block.
    return ColumnTransformer(
        [("num", numeric, spec.numeric), ("text", text, spec.text), ("cat", categorical, spec.categorical)],
        sparse_threshold=0.0,
    )


def source_feature(transformed_name: str, spec: FeatureSpec) -> str:
    """Map an output column (e.g. ``cat__region_west``) back to its input feature."""
    block, _, name = transformed_name.partition("__")
    if block == "text":
        return spec.text
    if block == "num":
        return name.removeprefix("missingindicator_")
    for col in sorted(spec.categorical, key=len, reverse=True):
        if name == col or name.startswith(col + "_"):
            return col
    return name
