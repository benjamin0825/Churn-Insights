"""Pure-NumPy reference implementations of the native kernels (same API as ``_native``)."""

from __future__ import annotations

import numpy as np


def group_stats(codes: np.ndarray, values: np.ndarray, n_groups: int):
    valid = codes >= 0
    c, v = codes[valid], values[valid]
    counts = np.bincount(c, minlength=n_groups).astype(np.int64)
    sums = np.column_stack([np.bincount(c, v[:, j], n_groups) for j in range(v.shape[1])])
    sumsq = np.column_stack([np.bincount(c, v[:, j] ** 2, n_groups) for j in range(v.shape[1])])
    return sums.reshape(n_groups, -1), sumsq.reshape(n_groups, -1), counts


def group_last(codes: np.ndarray, values: np.ndarray, n_groups: int):
    out = np.full((n_groups, values.shape[1]), np.nan)
    valid = np.flatnonzero(codes >= 0)
    out[codes[valid]] = values[valid]  # later rows overwrite earlier ones
    return out


def group_max_where(codes: np.ndarray, values: np.ndarray, mask: np.ndarray, n_groups: int):
    out = np.full(n_groups, -np.inf)
    keep = (codes >= 0) & mask.astype(bool)
    np.maximum.at(out, codes[keep], values[keep])
    out[np.isneginf(out)] = np.nan
    return out


def group_category_counts(codes: np.ndarray, categories: np.ndarray, n_groups: int, n_categories: int):
    keep = (codes >= 0) & (categories >= 0) & (categories < n_categories)
    flat = np.bincount(
        codes[keep].astype(np.int64) * n_categories + categories[keep], minlength=n_groups * n_categories
    )
    return flat.reshape(n_groups, n_categories).astype(np.int64)


def group_join(codes: np.ndarray, texts, n_groups: int, sep: str = " | "):
    parts: list[list[str] | None] = [None] * n_groups
    for g, text in zip(codes.tolist(), texts):
        if g < 0:
            continue
        if parts[g] is None:
            parts[g] = [text]
        else:
            parts[g].append(text)
    out = np.empty(n_groups, dtype=object)
    out[:] = ["" if p is None else sep.join(p) for p in parts]
    return out


def binned_frequencies(values: np.ndarray, edges: np.ndarray):
    nan = np.isnan(values)
    bins = np.searchsorted(edges, values[~nan], side="right")
    counts = np.bincount(bins, minlength=len(edges) + 1).astype(float)
    counts = np.append(counts, nan.sum())
    return counts / len(values) if len(values) else counts
