"""Native kernel engine (binary-only).

Compiled submodules, grouped by concern; the public API is re-exported here and
consumed through ``churn_ml.kernels``.
"""

from ._aggregate import group_last, group_stats
from ._binning import binned_frequencies
from ._counting import group_category_counts
from ._select import group_max_where
from ._text import group_join

__all__ = [
    "binned_frequencies",
    "group_category_counts",
    "group_join",
    "group_last",
    "group_max_where",
    "group_stats",
]
