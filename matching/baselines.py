"""
baselines.py

Baseline methods. They use the same pools and group sizes as the full method,
so group size cannot explain a difference between methods.

  random            shuffle the pool and cut it into groups
  single_attribute  shuffle, sort on one attribute (age_band or
                    primary_support_goal) and group consecutive profiles
  unweighted_gower  the full method with equal weights for every attribute

Group scores for the random and single-attribute baselines use the default
weights, so they can be compared with the full method. Profiles left over by
the size plan are the last ones in the shuffled or sorted order.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from matching.attributes import ATTRIBUTES, DEFAULT_WEIGHTS, equal_weights
from matching.group_assembly import GroupingResult, assemble_groups, describe_groups
from matching.hard_rules import plan_group_sizes
from matching.similarity import (
    compute_gower_distance_matrix, compute_unweighted_gower_distance_matrix,
)


def _cut(pool_df: pd.DataFrame, order: np.ndarray, method: str, pool_key: tuple,
         description: str) -> GroupingResult:
    ids = pool_df["profile_id"].tolist()
    result = GroupingResult(method=method, pool_key=tuple(pool_key))
    plan = plan_group_sizes(len(pool_df))
    result.log.append(f"plan: pool_size={len(pool_df)}, group_sizes={plan.sizes}, "
                      f"leftover={plan.leftover}")
    result.log.append(description)
    groups, start = [], 0
    for size in plan.sizes:
        groups.append([int(i) for i in order[start:start + size]])
        start += size
    result.unmatched = {ids[i]: plan.reason for i in order[start:]}
    if groups:
        distance = compute_gower_distance_matrix(pool_df, DEFAULT_WEIGHTS)
        result.scores, result.group_details = describe_groups(pool_df, groups, distance,
                                                              DEFAULT_WEIGHTS)
    result.groups = [[ids[i] for i in g] for g in groups]
    result.stopping = "not_applicable"
    return result


def random_assignment(pool_df: pd.DataFrame, seed: int = 0, pool_key: tuple = ()) -> GroupingResult:
    pool_df = pool_df.reset_index(drop=True)
    order = np.random.default_rng(seed).permutation(len(pool_df))
    return _cut(pool_df, order, "random", pool_key,
                f"random: seeded shuffle (seed={seed}), cut into groups")


def single_attribute(pool_df: pd.DataFrame, attribute: str, seed: int = 0,
                     pool_key: tuple = ()) -> GroupingResult:
    pool_df = pool_df.reset_index(drop=True)
    shuffled = np.random.default_rng(seed).permutation(len(pool_df))
    rank = {c: i for i, c in enumerate(ATTRIBUTES[attribute]["categories"])}
    keys = pool_df[attribute].map(rank).to_numpy()[shuffled]
    order = shuffled[np.argsort(keys, kind="stable")]
    return _cut(pool_df, order, f"single_{attribute}", pool_key,
                f"single_attribute: sorted by {attribute} (ties in seeded random order, "
                f"seed={seed}), consecutive members grouped")


def unweighted_gower(pool_df: pd.DataFrame, seed: int = 0, pool_key: tuple = ()) -> GroupingResult:
    pool_df = pool_df.reset_index(drop=True)
    distance = compute_unweighted_gower_distance_matrix(pool_df)
    return assemble_groups(pool_df, distance, equal_weights(), seed=seed,
                           method="unweighted_gower", pool_key=pool_key)
