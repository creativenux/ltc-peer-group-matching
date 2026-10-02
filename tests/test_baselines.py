"""Baselines: random, single-attribute (age band, support goal), unweighted
Gower. Same pools and same group-size procedure as the full method."""

import numpy as np
import pytest

from factories import make_profiles
from matching.attributes import ATTRIBUTES
from matching.baselines import random_assignment, single_attribute, unweighted_gower

AGES = ["18-29", "30-44", "45-59", "60-74", "75+"]
GOALS = ["emotional_support", "self_management_info", "social_connection",
         "accountability", "shared_activity"]


def varied(n, seed=0):
    rng = np.random.default_rng(seed)
    return make_profiles(n, age_band=list(rng.choice(AGES, n)),
                         primary_support_goal=list(rng.choice(GOALS, n)),
                         support_orientation=list(rng.choice(["Seeking", "Offering"], n)))


ALL_BASELINES = [
    lambda df, seed: random_assignment(df, seed=seed),
    lambda df, seed: single_attribute(df, "age_band", seed=seed),
    lambda df, seed: single_attribute(df, "primary_support_goal", seed=seed),
    lambda df, seed: unweighted_gower(df, seed=seed),
]


@pytest.mark.parametrize("baseline", ALL_BASELINES)
@pytest.mark.parametrize("n", [0, 5, 6, 9, 17, 23, 64])
def test_baselines_respect_group_size_and_place_everyone_once(baseline, n):
    df = varied(n)
    result = baseline(df, 0)
    assert all(6 <= len(g) <= 8 for g in result.groups)
    placed = [p for g in result.groups for p in g] + list(result.unmatched)
    assert sorted(placed) == sorted(df["profile_id"])


@pytest.mark.parametrize("baseline", ALL_BASELINES)
def test_baselines_use_the_same_group_sizes_as_the_full_method(baseline):
    from matching.hard_rules import plan_group_sizes
    result = baseline(varied(45), 0)
    assert sorted(len(g) for g in result.groups) == sorted(plan_group_sizes(45).sizes)


def test_random_is_reproducible_and_seed_dependent():
    df = varied(40)
    assert random_assignment(df, seed=1).groups == random_assignment(df, seed=1).groups
    assert random_assignment(df, seed=1).groups != random_assignment(df, seed=2).groups


@pytest.mark.parametrize("attribute", ["age_band", "primary_support_goal"])
def test_single_attribute_groups_are_consecutive_after_sorting(attribute):
    df = varied(60)
    result = single_attribute(df, attribute, seed=0)
    rank = {c: i for i, c in enumerate(ATTRIBUTES[attribute]["categories"])}
    lookup = dict(zip(df["profile_id"], df[attribute].map(rank)))
    ranges = [(min(lookup[p] for p in g), max(lookup[p] for p in g)) for g in result.groups]
    for (lo1, hi1), (lo2, hi2) in zip(ranges, ranges[1:]):
        assert hi1 <= lo2


def test_method_names():
    df = varied(14)
    assert random_assignment(df).method == "random"
    assert single_attribute(df, "age_band").method == "single_age_band"
    assert single_attribute(df, "primary_support_goal").method == "single_primary_support_goal"
    assert unweighted_gower(df).method == "unweighted_gower"
