"""
explainability.py

Turns each group's recorded details and each reason code into plain language.

For each group it reports:
  - the one or two attributes members share most (ties go to the higher weight)
  - the least similar pair of members
  - how balanced the group is on support orientation and isolation level:
    entropy >= 0.75 "well balanced", >= 0.40 "partly mixed", otherwise
    "dominated by one ..."
"""

from __future__ import annotations

import re

from matching.attributes import ATTRIBUTES, DEFAULT_WEIGHTS

WELL_BALANCED = 0.75
PARTLY_MIXED = 0.40


def _label(attribute: str) -> str:
    return ATTRIBUTES[attribute]["label"]


def _balance_text(attribute: str, entropy: float, composition: dict) -> str:
    label = _label(attribute)
    if entropy >= WELL_BALANCED:
        return f"well balanced across {label}"
    if entropy >= PARTLY_MIXED:
        return f"partly mixed on {label}"
    top = max(composition, key=composition.get)
    share = "all" if len(composition) == 1 else "mostly"
    return f"dominated by one {label} ({share} {top})"


def explain_group(detail: dict) -> dict:
    """Plain-language explanation of one group from its recorded details."""
    similarity = detail["homogeneity_similarity"]
    ranked = sorted(similarity, key=lambda a: (-round(similarity[a], 9), -DEFAULT_WEIGHTS[a], a))
    strongest = ranked[:2]
    parts = [f"{_label(a)} (average pairwise similarity {similarity[a]:.0%})" for a in strongest]
    summary = "This group is held together most by shared " + " and ".join(parts) + "."

    a, b = detail["weakest_link"]["pair"]
    weakest = (f"The least similar pair is {a} and {b} "
               f"(Gower distance {detail['weakest_link']['distance']:.2f}).")

    balance = {attr: _balance_text(attr, h, detail["complementarity_composition"][attr])
               for attr, h in detail["complementarity_entropy"].items()}
    return {
        "summary": summary,
        "strongest_attributes": strongest,
        "weakest_link": weakest,
        "balance": balance,
    }


def _fields(reason: str) -> dict:
    return dict(re.findall(r"(\w+)=([^,;]+)", reason))


def explain_unmatched(reason: str) -> str:
    """Plain-language rendering of a hard-rule or size-plan reason code."""
    code = reason.split(":", 1)[0]
    f = _fields(reason)
    if code == "pool_too_small" and "category" in f:
        return (f"Not grouped: only {f['pool_size']} people share the {f['category']} condition "
                f"category and the {f['language']} language, and a group needs at least "
                f"{f['minimum_required']}.")
    if code == "pool_too_small":
        return (f"Not grouped: the pool has only {f['pool_size']} people, and a group needs at "
                f"least {f['minimum_required']}.")
    if code == "remainder_not_absorbable":
        left = re.search(r"(\d+) left over", reason)
        return (f"Not grouped: a pool of {f['pool_size'].split()[0]} people cannot be split into "
                f"groups of 6 to 8 without leaving someone out; {left.group(1) if left else 'some'} "
                f"left over after forming as many full groups as possible.")
    if code == "not_adult":
        return (f"Not eligible: age band {f['age_band']} is below the minimum age of "
                f"{f['minimum_age']}.")
    return reason
