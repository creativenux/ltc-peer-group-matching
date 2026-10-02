"""
statistical_tests.py

Compares methods across replicate datasets, one metric at a time.

  1. Friedman test across all methods, with Kendall's W = chi2 / (N (k - 1))
     as effect size.
  2. If significant (p < 0.05), Wilcoxon signed-rank tests of weighted Gower
     against each baseline, with Holm correction and the matched-pairs
     rank-biserial correlation as effect size.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import friedmanchisquare, rankdata, wilcoxon

ALPHA = 0.05


def holm_adjust(p_values) -> list:
    """Holm-Bonferroni adjusted p-values, in the original order."""
    p = np.asarray(p_values, float)
    m = len(p)
    order = np.argsort(p)
    adjusted = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adjusted[i] = running
    return adjusted.tolist()


def rank_biserial(x, y) -> float:
    """Matched-pairs rank-biserial correlation for x - y; zero differences dropped."""
    d = np.asarray(x, float) - np.asarray(y, float)
    d = d[d != 0]
    if len(d) == 0:
        return 0.0
    ranks = rankdata(np.abs(d))
    return float((ranks[d > 0].sum() - ranks[d < 0].sum()) / ranks.sum())


def kendalls_w(table: dict):
    """Friedman chi-square, its p-value, and Kendall's W for {method: values}."""
    columns = list(table.values())
    stat, p = friedmanchisquare(*columns)
    n, k = len(columns[0]), len(columns)
    return float(stat), float(p), float(stat / (n * (k - 1)))


def effect_label(r: float) -> str:
    r = abs(r)
    if r < 0.1:
        return "negligible"
    if r < 0.3:
        return "small"
    if r < 0.5:
        return "medium"
    return "large"


def _p_text(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def compare_methods(table: dict, reference: str, higher_is_better: bool) -> dict:
    """Friedman across all methods, then reference vs each baseline.

    table maps method name to its per-replicate values (same replicate order
    for every method).
    """
    values = np.array(list(table.values()), float)
    if np.all(values == values[:1, :]):
        return {"friedman": None, "pairwise": [],
                "note": "All methods have identical values within every replicate; no test is needed."}

    stat, p, w = kendalls_w(table)
    friedman = {"statistic": stat, "p_value": p, "kendalls_w": w,
                "interpretation": (f"The methods {'differ' if p < ALPHA else 'do not differ significantly'} "
                                   f"(Friedman chi-square = {stat:.2f}, {_p_text(p)}, "
                                   f"Kendall's W = {w:.2f}).")}
    if p >= ALPHA:
        return {"friedman": friedman, "pairwise": [],
                "note": "Friedman test not significant, so no pairwise tests were run."}

    baselines = [m for m in table if m != reference]
    raw, rows = [], []
    for b in baselines:
        x, y = np.asarray(table[reference], float), np.asarray(table[b], float)
        raw.append(float(wilcoxon(x, y).pvalue) if np.any(x != y) else 1.0)
        rows.append({"baseline": b, "median_difference": float(np.median(x - y)),
                     "rank_biserial": rank_biserial(x, y)})
    for row, p_raw, p_holm in zip(rows, raw, holm_adjust(raw)):
        row["p_value"], row["p_holm"] = p_raw, p_holm
        r = row["rank_biserial"]
        label = effect_label(r)
        row["effect_size"] = label
        reference_ahead = (r > 0) == higher_is_better
        if p_holm < ALPHA:
            verdict = f"{reference} is {'better' if reference_ahead else 'worse'} than {row['baseline']}"
        else:
            verdict = f"no significant difference between {reference} and {row['baseline']}"
        row["interpretation"] = (f"{verdict} (median difference {row['median_difference']:+.4f}, "
                                 f"Holm-adjusted {_p_text(p_holm)}, rank-biserial r = {r:.2f}, "
                                 f"{label} effect).")
    return {"friedman": friedman, "pairwise": rows, "note": ""}
