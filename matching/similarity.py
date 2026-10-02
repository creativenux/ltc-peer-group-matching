"""
similarity.py

Weighted Gower distance (Gower, 1971; Liu et al., 2024), written here rather
than taken from a package so the weighting is easy to check.

    d(i, j) = sum_k w_k * s_ijk / sum_k w_k

  nominal:  s = 0 if equal, else 1
  ordinal:  s = |rank_i - rank_j| / (number of categories - 1)
  numeric:  s = |x_i - x_j| / range within the pool (0 if the range is 0)

Only homogeneity attributes are used. Support orientation and the isolation
score should be mixed within a group rather than shared (Cruz & Isotani,
2014), so they are scored at group level in group_assembly.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from matching.attributes import (
    ATTRIBUTES, NOMINAL, ORDINAL, NUMERIC, HOMOGENEITY_ATTRIBUTES, homogeneity_weights,
)


def attribute_dissimilarity(pool_df: pd.DataFrame, attribute: str) -> np.ndarray:
    """n x n per-attribute dissimilarity s_ijk in [0, 1]."""
    spec = ATTRIBUTES[attribute]
    values = pool_df[attribute].to_numpy()

    if spec["type"] == NOMINAL:
        return (values[:, None] != values[None, :]).astype(float)

    if spec["type"] == ORDINAL:
        order = {c: r for r, c in enumerate(spec["categories"])}
        ranks = np.array([order[v] for v in values], dtype=float)
        return np.abs(ranks[:, None] - ranks[None, :]) / (len(order) - 1)

    if spec["type"] == NUMERIC:
        x = values.astype(float)
        span = x.max() - x.min() if len(x) else 0.0
        if span == 0:
            return np.zeros((len(x), len(x)))
        return np.abs(x[:, None] - x[None, :]) / span

    raise ValueError(f"unknown attribute type for {attribute}")


def gower_distance_matrix(pool_df: pd.DataFrame, weights: dict) -> np.ndarray:
    """Weighted Gower distance over exactly the attributes named in weights."""
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("weights sum to zero")
    n = len(pool_df)
    d = np.zeros((n, n))
    for attribute, w in weights.items():
        if w:
            d += w * attribute_dissimilarity(pool_df, attribute)
    return d / total


def compute_gower_distance_matrix(pool_df: pd.DataFrame, weights: dict) -> np.ndarray:
    """n x n weighted Gower distance for one eligible pool, using only the
    homogeneity attributes, their weights renormalised to sum to 1."""
    return gower_distance_matrix(pool_df, homogeneity_weights(weights))


def compute_unweighted_gower_distance_matrix(pool_df: pd.DataFrame) -> np.ndarray:
    """As compute_gower_distance_matrix, but every homogeneity attribute has
    equal weight (the unweighted-Gower baseline)."""
    return gower_distance_matrix(pool_df, {a: 1.0 for a in HOMOGENEITY_ATTRIBUTES})
