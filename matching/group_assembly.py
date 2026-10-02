"""
group_assembly.py

Forms groups of 6 to 8 inside one pool.

Group score:

    Score(G) = sum over H of w_a * mean pairwise similarity on a
             + sum over C of w_a * normalised entropy of a in G

H are the homogeneity attributes and C the complementarity attributes
(support orientation, and the isolation score in four bands). The homogeneity
part equals (sum of H weights) * (1 - mean weighted Gower distance), so it
comes straight from the distance matrix.

Steps:
  1. Group sizes come from hard_rules.plan_group_sizes.
  2. Greedy: take the pool in a seeded random order, start one group with each
     of the first k profiles, then add every other profile to the open group
     where it adds most (mean similarity to members plus change in entropy).
     A change in Score is undefined for a one-member group, which has no
     pairs, so this marginal form is used instead.
  3. Local swap: score every swap between members of different groups at
     once, apply the best improving swaps (at most one per group), and repeat
     until no swap helps or 200 passes. Swaps keep group sizes the same.

Each group is stored with the details the explainability layer needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from matching.attributes import (
    ATTRIBUTES, HOMOGENEITY_ATTRIBUTES, COMPLEMENTARITY_ATTRIBUTES, NUMERIC,
    isolation_band,
)
from matching.hard_rules import plan_group_sizes
from matching.similarity import attribute_dissimilarity

IMPROVEMENT_TOLERANCE = 1e-10
MAX_PASSES = 200


@dataclass
class GroupingResult:
    method: str
    pool_key: tuple
    groups: list = field(default_factory=list)          # lists of profile_ids
    unmatched: dict = field(default_factory=dict)       # profile_id -> reason
    scores: list = field(default_factory=list)          # Score(G) per group
    group_details: list = field(default_factory=list)   # per-group breakdown
    log: list = field(default_factory=list)
    stopping: str = "not_run"
    passes: int = 0
    swaps: int = 0
    total_score_after_greedy: float = 0.0
    total_score_after_swaps: float = 0.0


# =============================================================================
# COMPLEMENTARITY CODING AND ENTROPY
# =============================================================================

def complementarity_codes(pool_df: pd.DataFrame) -> dict:
    """attribute -> (integer category codes, number of categories)."""
    codes = {}
    for attribute in COMPLEMENTARITY_ATTRIBUTES:
        spec = ATTRIBUTES[attribute]
        cats = spec["categories"]
        index = {c: i for i, c in enumerate(cats)}
        values = pool_df[attribute]
        if spec["type"] == NUMERIC:
            values = values.map(isolation_band)
        codes[attribute] = (np.array([index[v] for v in values], dtype=int), len(cats))
    return codes


def normalised_entropy(counts: np.ndarray, n_categories: int) -> np.ndarray:
    """Shannon entropy of category counts (last axis), divided by log(K)."""
    counts = np.asarray(counts, dtype=float)
    total = counts.sum(axis=-1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = np.where(total > 0, counts / total, 0.0)
        terms = np.where(p > 0, -p * np.log(p), 0.0)
    return terms.sum(axis=-1) / np.log(n_categories)


def _counts(codes: np.ndarray, members, n_categories: int) -> np.ndarray:
    return np.bincount(codes[members], minlength=n_categories)


# =============================================================================
# OBJECTIVE
# =============================================================================

def _h_weight(weights: dict) -> float:
    return sum(weights[a] for a in HOMOGENEITY_ATTRIBUTES)


def _score(members, distance, codes, weights) -> float:
    members = list(members)
    m = len(members)
    if m >= 2:
        sub = distance[np.ix_(members, members)]
        mean_distance = sub[np.triu_indices(m, 1)].mean()
        h_part = _h_weight(weights) * (1.0 - mean_distance)
    else:
        h_part = 0.0
    c_part = sum(weights[a] * float(normalised_entropy(_counts(c, members, k), k))
                 for a, (c, k) in codes.items())
    return h_part + c_part


def score_group(pool_df: pd.DataFrame, distance_matrix: np.ndarray, weights: dict,
                member_positions) -> float:
    """Score(G) for the group made of the given row positions of pool_df."""
    return _score(member_positions, distance_matrix, complementarity_codes(pool_df), weights)


# =============================================================================
# GREEDY CONSTRUCTION
# =============================================================================

def _greedy(n, sizes, distance, codes, weights, rng, log):
    order = rng.permutation(n)
    k = len(sizes)
    groups = [[int(i)] for i in order[:k]]
    log.append(f"greedy: seeded {k} groups with positions {order[:k].tolist()} "
               f"(seeded permutation)")
    h_weight = _h_weight(weights)
    counts = {a: np.array([_counts(c, g, kk) for g in groups]) for a, (c, kk) in codes.items()}
    leftovers = []
    for x in order[k:]:
        x = int(x)
        open_groups = [g for g in range(k) if len(groups[g]) < sizes[g]]
        if not open_groups:
            leftovers.append(x)
            continue
        best, best_gain = None, -np.inf
        for g in open_groups:
            gain = h_weight * (1.0 - distance[x, groups[g]].mean())
            for a, (c, kk) in codes.items():
                before = counts[a][g]
                after = before.copy()
                after[c[x]] += 1
                gain += weights[a] * (normalised_entropy(after, kk) - normalised_entropy(before, kk))
            if gain > best_gain + IMPROVEMENT_TOLERANCE:
                best, best_gain = g, gain
        groups[best].append(x)
        for a, (c, _) in codes.items():
            counts[a][best][c[x]] += 1
    return groups, leftovers


# =============================================================================
# LOCAL-SWAP REFINEMENT
# =============================================================================

def _entropy_swap_table(counts: np.ndarray, n_categories: int) -> np.ndarray:
    """T[g, out, in]: change in normalised entropy of group g when one member
    of category `out` is replaced by one of category `in`."""
    k = counts.shape[0]
    eye = np.eye(n_categories, dtype=int)
    after = counts[:, None, None, :] - eye[None, :, None, :] + eye[None, None, :, :]
    base = normalised_entropy(counts, n_categories)[:, None, None]
    table = normalised_entropy(np.clip(after, 0, None), n_categories) - base
    # Replacing with the same category changes nothing.
    table[:, np.arange(n_categories), np.arange(n_categories)] = 0.0
    return table.reshape(k, n_categories, n_categories)


def _swap_deltas(labels, similarity, pair_counts, codes, weights):
    """Delta in total Score for swapping every pair (a, b) of matched members."""
    k = len(pair_counts)
    onehot = np.zeros((len(labels), k))
    onehot[np.arange(len(labels)), labels] = 1.0
    R = similarity @ onehot                      # R[i, g] = sum_{j in g} sim(i, j)
    Rl = R[:, labels]                            # Rl[i, j] = R[i, group of j]
    own = R[np.arange(len(labels)), labels]      # own-group sum, includes sim(i,i) = 1
    d_sum_a = Rl.T - similarity - own[:, None] + 1.0   # change in pair-sum of a's group
    d_sum_b = Rl - similarity - own[None, :] + 1.0     # change in pair-sum of b's group
    P = pair_counts[labels]
    delta = _h_weight(weights) * (d_sum_a / P[:, None] + d_sum_b / P[None, :])
    for a, (c, kk) in codes.items():
        counts = np.array([np.bincount(c[labels == g], minlength=kk) for g in range(k)])
        T = _entropy_swap_table(counts, kk)
        delta += weights[a] * (T[labels[:, None], c[:, None], c[None, :]]
                               + T[labels[None, :], c[None, :], c[:, None]])
    same = labels[:, None] == labels[None, :]
    delta[same] = -np.inf
    return np.triu(delta, 1) + np.tril(np.full_like(delta, -np.inf))


def _local_swap(groups, distance, codes, weights, max_passes, log):
    matched = [i for g in groups for i in g]
    pos = {p: i for i, p in enumerate(matched)}
    labels = np.array([gi for gi, g in enumerate(groups) for _ in g])
    sub_codes = {a: (c[matched], kk) for a, (c, kk) in codes.items()}
    similarity = 1.0 - distance[np.ix_(matched, matched)]
    sizes = np.bincount(labels, minlength=len(groups))
    pair_counts = sizes * (sizes - 1) / 2.0

    passes, swaps, stopping = 0, 0, "converged"
    while True:
        if passes >= max_passes:
            stopping = "max_passes_reached"
            break
        delta = _swap_deltas(labels, similarity, pair_counts, sub_codes, weights)
        a_idx, b_idx = np.nonzero(delta > IMPROVEMENT_TOLERANCE)
        passes += 1
        if len(a_idx) == 0:
            break
        order = np.argsort(-delta[a_idx, b_idx], kind="stable")
        used = set()
        applied = 0
        for o in order:
            a, b = int(a_idx[o]), int(b_idx[o])
            ga, gb = int(labels[a]), int(labels[b])
            if ga in used or gb in used:
                continue
            labels[a], labels[b] = gb, ga
            used.update((ga, gb))
            applied += 1
        swaps += applied
    log.append(f"local_swap: {passes} pass(es), {swaps} swap(s), stopping={stopping}")
    new_groups = [[matched[i] for i in np.nonzero(labels == g)[0]] for g in range(len(groups))]
    return new_groups, passes, swaps, stopping


# =============================================================================
# GROUP DETAILS (for explainability)
# =============================================================================

def _group_details(pool_df, members, distance, codes):
    sub = pool_df.iloc[members]
    m = len(members)
    iu = np.triu_indices(m, 1)
    homogeneity = {a: float(1.0 - attribute_dissimilarity(sub, a)[iu].mean())
                   for a in HOMOGENEITY_ATTRIBUTES}
    entropy = {}
    composition = {}
    for a, (c, kk) in codes.items():
        counts = _counts(c, members, kk)
        entropy[a] = float(normalised_entropy(counts, kk))
        composition[a] = {ATTRIBUTES[a]["categories"][i]: int(n) for i, n in enumerate(counts) if n}
    dsub = distance[np.ix_(members, members)]
    i, j = np.unravel_index(np.argmax(np.triu(dsub, 1)), dsub.shape)
    ids = sub["profile_id"].tolist()
    return {
        "homogeneity_similarity": homogeneity,
        "complementarity_entropy": entropy,
        "complementarity_composition": composition,
        "mean_distance": float(dsub[iu].mean()),
        "weakest_link": {"pair": [ids[i], ids[j]], "distance": float(dsub[i, j])},
    }


def describe_groups(pool_df: pd.DataFrame, groups: list, distance_matrix: np.ndarray,
                    weights: dict) -> tuple:
    """Score(G) and the explainability breakdown for groups given as row
    positions of pool_df. Shared by the full method and the baselines so
    every method is described in exactly the same way."""
    codes = complementarity_codes(pool_df)
    scores = [_score(g, distance_matrix, codes, weights) for g in groups]
    details = [_group_details(pool_df, g, distance_matrix, codes) for g in groups]
    return scores, details


# =============================================================================
# ENTRY POINT
# =============================================================================

def assemble_groups(pool_df: pd.DataFrame, distance_matrix: np.ndarray, weights: dict,
                    seed: int = 0, max_passes: int = MAX_PASSES,
                    method: str = "weighted_gower", pool_key: tuple = ()) -> GroupingResult:
    """Form groups of 6 to 8 inside one pool.

    Returns a GroupingResult with the groups (lists of profile_ids), the
    unmatched profile_ids with reasons, Score(G) for every group, per-group
    details for the explainability layer, and a log of construction and swap
    decisions.
    """
    pool_df = pool_df.reset_index(drop=True)
    ids = pool_df["profile_id"].tolist()
    result = GroupingResult(method=method, pool_key=tuple(pool_key))
    plan = plan_group_sizes(len(pool_df))
    result.log.append(f"plan: pool_size={len(pool_df)}, group_sizes={plan.sizes}, "
                      f"leftover={plan.leftover}")
    if not plan.sizes:
        result.unmatched = {pid: plan.reason for pid in ids}
        return result

    codes = complementarity_codes(pool_df)
    rng = np.random.default_rng(seed)
    groups, leftovers = _greedy(len(pool_df), plan.sizes, distance_matrix, codes, weights,
                                rng, result.log)
    result.total_score_after_greedy = sum(_score(g, distance_matrix, codes, weights) for g in groups)

    groups, result.passes, result.swaps, result.stopping = _local_swap(
        groups, distance_matrix, codes, weights, max_passes, result.log)

    result.scores, result.group_details = describe_groups(pool_df, groups, distance_matrix, weights)
    result.total_score_after_swaps = sum(result.scores)
    result.groups = [[ids[i] for i in g] for g in groups]
    result.unmatched = {ids[i]: plan.reason for i in leftovers}
    return result
