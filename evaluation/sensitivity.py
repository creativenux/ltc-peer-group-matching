"""
sensitivity.py

Weight sensitivity analysis. Each weight is raised and lowered by 10%, the
other weights are rescaled to sum to 1, and the weighted method is re-run on
the same dataset. The new grouping is compared with the original using the
Adjusted Rand Index (Hubert & Arabie, 1985), where 1 means identical groups.

Two reference points: the ARI between two runs that differ only in seed, and
each grouping's within-group distance under the original weights, which shows
whether group quality changes when membership does.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

from matching.attributes import DEFAULT_WEIGHTS, MIN_GROUP_SIZE
from matching.group_assembly import assemble_groups
from matching.hard_rules import partition_into_eligible_pools
from matching.similarity import compute_gower_distance_matrix

PERTURBATION = 0.10


def set_weight(weights: dict, attribute: str, value: float) -> dict:
    """Set one weight to value and rescale the others proportionally so all
    weights sum to 1. If the others are all zero, the remainder is shared
    equally between them."""
    others = {a: w for a, w in weights.items() if a != attribute}
    rest = sum(others.values())
    remainder = 1.0 - value
    if rest > 0:
        scaled = {a: w * remainder / rest for a, w in others.items()}
    else:
        scaled = {a: remainder / len(others) for a in others}
    return {a: value if a == attribute else scaled[a] for a in weights}


def perturb_weight(weights: dict, attribute: str, fraction: float) -> dict:
    """Change one weight by the given fraction (e.g. +0.10) and renormalise."""
    return set_weight(weights, attribute, weights[attribute] * (1.0 + fraction))


def weighted_grouping(df: pd.DataFrame, seed: int, weights: dict) -> list:
    """Groups (lists of profile_ids) from the weighted method with the given weights."""
    pools, _ = partition_into_eligible_pools(df)
    groups = []
    for key, pool in pools.items():
        if len(pool) < MIN_GROUP_SIZE:
            continue
        pool = pool.reset_index(drop=True)
        result = assemble_groups(pool, compute_gower_distance_matrix(pool, weights), weights,
                                 seed=seed, pool_key=key)
        groups.extend(result.groups)
    return groups


def grouping_ari(groups_a: list, groups_b: list) -> float:
    """Adjusted Rand Index over the profiles grouped in both groupings."""
    label_a = {p: i for i, g in enumerate(groups_a) for p in g}
    label_b = {p: i for i, g in enumerate(groups_b) for p in g}
    common = sorted(set(label_a) & set(label_b))
    return float(adjusted_rand_score([label_a[p] for p in common], [label_b[p] for p in common]))


def within_group_distance(df: pd.DataFrame, groups: list, weights: dict) -> float:
    """Mean pairwise weighted Gower distance inside groups, under the given weights."""
    pools, _ = partition_into_eligible_pools(df)
    pool_of = {pid: key for key, pool in pools.items() for pid in pool["profile_id"]}
    cache = {}
    values = []
    for g in groups:
        key = pool_of[g[0]]
        if key not in cache:
            pool = pools[key].reset_index(drop=True)
            cache[key] = ({pid: i for i, pid in enumerate(pool["profile_id"])},
                          compute_gower_distance_matrix(pool, weights))
        position, distance = cache[key]
        idx = [position[p] for p in g]
        values.append(distance[np.ix_(idx, idx)][np.triu_indices(len(idx), 1)].mean())
    return float(np.mean(values)) if values else float("nan")


def _job(args):
    df, seed, weights = args
    return weighted_grouping(df, seed, weights)


def run_sensitivity(df: pd.DataFrame, seed: int, weights: dict = DEFAULT_WEIGHTS,
                    workers: int = 1) -> dict:
    """Perturb every weight by +/-10% and compare each grouping with the original."""
    total = sum(weights.values())
    base_weights = {a: w / total for a, w in weights.items()}  # sum exactly 1
    jobs = [(df, seed, base_weights), (df, seed + 1, base_weights)]
    cases = []
    for attribute in weights:
        for fraction in (+PERTURBATION, -PERTURBATION):
            cases.append((attribute, fraction))
            jobs.append((df, seed, perturb_weight(base_weights, attribute, fraction)))

    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            groupings = list(pool.map(_job, jobs))
    else:
        groupings = [_job(j) for j in jobs]

    base, other_seed, perturbed = groupings[0], groupings[1], groupings[2:]
    rows = [{"attribute": a, "direction": f"{fraction:+.0%}",
             "weight": jobs[i + 2][2][a], "ari": grouping_ari(base, g),
             "within_group_distance": within_group_distance(df, g, base_weights)}
            for i, ((a, fraction), g) in enumerate(zip(cases, perturbed))]

    ranking = []
    for attribute in weights:
        aris = [r["ari"] for r in rows if r["attribute"] == attribute]
        ranking.append({"attribute": attribute, "original_weight": base_weights[attribute],
                        "ari_plus": aris[0], "ari_minus": aris[1],
                        "mean_change": 1.0 - sum(aris) / 2})
    ranking.sort(key=lambda r: -r["mean_change"])
    return {"seed": seed, "perturbation": PERTURBATION, "perturbations": rows,
            "ranking": ranking, "seed_reference_ari": grouping_ari(base, other_seed),
            "base_within_group_distance": within_group_distance(df, base, base_weights),
            "seed_reference_within_group_distance": within_group_distance(df, other_seed,
                                                                          base_weights)}
