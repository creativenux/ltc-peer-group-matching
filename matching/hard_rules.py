"""
hard_rules.py

Hard rules, applied before any similarity is measured:

  1. Adult: the age band must start at 18 or above. Every generated profile
     passes, but the rule is still checked and logged.
  2. Same condition category.
  3. Same communication language.
     Rules 2 and 3 split the dataset into pools; groups never cross pools.
  4. Group size 6 to 8 (plan_group_sizes).

Every profile that cannot be grouped gets a named reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from matching.attributes import MIN_GROUP_SIZE, MAX_GROUP_SIZE, TARGET_GROUP_SIZE, POOL_KEYS

ADULT_AGE = 18


# =============================================================================
# RULE 4: GROUP SIZE
# =============================================================================

@dataclass
class GroupSizePlan:
    sizes: list          # target size of each group, each in [6, 8]
    leftover: int        # profiles that cannot be placed without breaking [6, 8]
    reason: str = ""     # why there is a leftover, empty when leftover == 0


def plan_group_sizes(pool_size: int) -> GroupSizePlan:
    """Split a pool as evenly as possible into groups of 6 to 8.

    The number of groups is round(n / 7), rounded half-up and kept within
    [ceil(n/8), floor(n/6)]. When no valid number exists (n < 6, or n in
    {9, 10, 11, 17}), as many groups of 8 as possible are formed and the rest
    are recorded as left over.
    """
    n = pool_size
    if n < MIN_GROUP_SIZE:
        reason = f"pool_too_small: pool_size={n}, minimum_required={MIN_GROUP_SIZE}" if n else ""
        return GroupSizePlan([], n, reason)

    k = int(n / TARGET_GROUP_SIZE + 0.5)
    k_min = -(-n // MAX_GROUP_SIZE)
    k_max = n // MIN_GROUP_SIZE
    if k_min <= k_max:
        k = min(max(k, k_min), k_max)
        base, extra = divmod(n, k)
        sizes = [base + 1] * extra + [base] * (k - extra)
        return GroupSizePlan(sizes, 0)

    k = k_max
    leftover = n - k * MAX_GROUP_SIZE
    reason = (f"remainder_not_absorbable: pool_size={n} cannot be divided into groups "
              f"of {MIN_GROUP_SIZE} to {MAX_GROUP_SIZE}; {leftover} left over")
    return GroupSizePlan([MAX_GROUP_SIZE] * k, leftover, reason)


# =============================================================================
# RULES 1 TO 3: ELIGIBLE POOLS
# =============================================================================

@dataclass
class HardRuleAudit:
    rules: list = field(default_factory=list)     # one entry per rule
    pools: list = field(default_factory=list)     # one entry per pool
    excluded: dict = field(default_factory=dict)  # profile_id -> reason


def _band_lower_bound(band: str) -> int:
    return int(str(band).replace("+", "").split("-")[0])


def partition_into_eligible_pools(df: pd.DataFrame):
    """Partition profiles into eligible pools keyed by (condition_category, language).

    Returns (pools, audit). pools maps (primary_condition_category,
    communication_language) to the sub-DataFrame of eligible profiles sharing
    both. audit records every rule (including those that excluded no one),
    every pool's size and viability, and a named reason for every profile
    that cannot be grouped at this stage.
    """
    audit = HardRuleAudit()

    # Rule 1: adult eligibility.
    lower = df["age_band"].map(_band_lower_bound)
    not_adult = df[lower < ADULT_AGE]
    for pid, band in zip(not_adult["profile_id"], not_adult["age_band"]):
        audit.excluded[pid] = f"not_adult: age_band={band}, minimum_age={ADULT_AGE}"
    audit.rules.append({
        "rule": "adult_eligibility", "status": "applied",
        "checked": len(df), "excluded": len(not_adult),
        "note": "Every generated profile is an adult; the rule is still checked and logged.",
    })
    adults = df[lower >= ADULT_AGE]

    # Rules 2 and 3: shared condition category and shared language. These
    # never exclude anyone by themselves; they decide who may be grouped
    # together.
    pools = {key: pool for key, pool in adults.groupby(list(POOL_KEYS), sort=True)}
    for rule in ("shared_condition_category", "shared_communication_language"):
        audit.rules.append({
            "rule": rule, "status": "applied", "checked": len(adults), "excluded": 0,
            "note": "Partitions profiles into pools; groups never cross pools.",
        })

    # Pool viability: a pool smaller than the minimum group size cannot form
    # even one group.
    for (category, language), pool in pools.items():
        viable = len(pool) >= MIN_GROUP_SIZE
        audit.pools.append({"category": category, "language": language,
                            "size": len(pool), "viable": viable})
        if not viable:
            reason = (f"pool_too_small: category={category}, language={language}, "
                      f"pool_size={len(pool)}, minimum_required={MIN_GROUP_SIZE}")
            for pid in pool["profile_id"]:
                audit.excluded[pid] = reason
    audit.rules.append({
        "rule": "group_size", "status": "applied", "checked": len(adults),
        "excluded": sum(p["size"] for p in audit.pools if not p["viable"]),
        "note": f"Groups must have {MIN_GROUP_SIZE} to {MAX_GROUP_SIZE} members.",
    })
    return pools, audit
