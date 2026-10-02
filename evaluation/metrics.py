"""
metrics.py

Cohesion metrics, computed the same way for every method:

  silhouette_weighted    silhouette (Rousseeuw, 1987) on the weighted Gower matrix
  silhouette_unweighted  silhouette on the unweighted Gower matrix, as a check,
                         because the weighted method optimises the weighted matrix
  within_group_distance  mean weighted Gower distance between group members
                         (lower is better), plus the same for each attribute
  cohesion_index         mean group score under the default weights
  unmatched_rate         share of profiles not placed in a group

Silhouette is computed within each pool and averaged, weighted by the number
of grouped profiles. Pools with only one group are skipped.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import silhouette_score

from matching.attributes import DEFAULT_WEIGHTS, HOMOGENEITY_ATTRIBUTES
from matching.group_assembly import describe_groups
from matching.similarity import (
    attribute_dissimilarity, compute_gower_distance_matrix,
    compute_unweighted_gower_distance_matrix,
)


def _weighted_mean(values, weights) -> float:
    values, weights = np.asarray(values, float), np.asarray(weights, float)
    return float((values * weights).sum() / weights.sum()) if weights.sum() else float("nan")


def _silhouette(distance, positions_by_group):
    members = [p for g in positions_by_group for p in g]
    labels = [i for i, g in enumerate(positions_by_group) for _ in g]
    sub = distance[np.ix_(members, members)]
    return silhouette_score(sub, labels, metric="precomputed"), len(members)


def evaluate_run(run) -> dict:
    """Metrics for every method in a MatchingRun, keyed by method name."""
    # Distance matrices are shared by all methods, so compute them once per pool.
    cache = {}
    for key, pool in run.pools.items():
        pool = pool.reset_index(drop=True)
        cache[key] = {
            "pool": pool,
            "position": {pid: i for i, pid in enumerate(pool["profile_id"])},
            "weighted": compute_gower_distance_matrix(pool, DEFAULT_WEIGHTS),
            "unweighted": compute_unweighted_gower_distance_matrix(pool),
            "per_attribute": {a: attribute_dissimilarity(pool, a) for a in HOMOGENEITY_ATTRIBUTES},
        }

    results = {}
    for method, outcome in run.methods.items():
        sil_w, sil_u, sil_n = [], [], []
        scores, within, per_attribute = [], [], {a: [] for a in HOMOGENEITY_ATTRIBUTES}
        for result in outcome.pool_results:
            c = cache[result.pool_key]
            groups = [[c["position"][pid] for pid in g] for g in result.groups]
            if not groups:
                continue
            group_scores, _ = describe_groups(c["pool"], groups, c["weighted"], DEFAULT_WEIGHTS)
            scores.extend(group_scores)
            for g in groups:
                iu = np.triu_indices(len(g), 1)
                within.append(c["weighted"][np.ix_(g, g)][iu].mean())
                for a in HOMOGENEITY_ATTRIBUTES:
                    per_attribute[a].append(c["per_attribute"][a][np.ix_(g, g)][iu].mean())
            if len(groups) >= 2:
                sw, n = _silhouette(c["weighted"], groups)
                su, _ = _silhouette(c["unweighted"], groups)
                sil_w.append(sw)
                sil_u.append(su)
                sil_n.append(n)

        results[method] = {
            "silhouette_weighted": _weighted_mean(sil_w, sil_n),
            "silhouette_unweighted": _weighted_mean(sil_u, sil_n),
            "within_group_distance": float(np.mean(within)) if within else float("nan"),
            "within_group_dissimilarity": {a: float(np.mean(v)) if v else float("nan")
                                           for a, v in per_attribute.items()},
            "cohesion_index": float(np.mean(scores)) if scores else float("nan"),
            "unmatched_rate": len(outcome.unmatched) / run.n_profiles if run.n_profiles else 0.0,
            "n_groups": len(outcome.groups),
        }
    return results
