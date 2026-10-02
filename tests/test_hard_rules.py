"""Hard rules: adult eligibility, shared condition category, shared language,
group size 6 to 8."""

import pytest

from factories import make_profiles, concat
from matching.hard_rules import plan_group_sizes, partition_into_eligible_pools


# ---- Rule 4: group size ------------------------------------------------------

@pytest.mark.parametrize("pool_size, sizes, leftover", [
    (0, [], 0),
    (5, [], 5),          # too small for even one group
    (6, [6], 0),         # exactly the minimum
    (7, [7], 0),
    (8, [8], 0),         # exactly the maximum
    (9, [8], 1),         # past the maximum, cannot split into two groups of 6
    (11, [8], 3),
    (12, [6, 6], 0),
    (14, [7, 7], 0),
    (17, [8, 8], 1),     # 17 cannot be written as a sum of 6s, 7s and 8s
    (18, [6, 6, 6], 0),
])
def test_plan_group_sizes_boundaries(pool_size, sizes, leftover):
    plan = plan_group_sizes(pool_size)
    assert plan.sizes == sizes
    assert plan.leftover == leftover


def test_plan_group_sizes_respects_bounds_and_conserves_profiles():
    for n in range(0, 400):
        plan = plan_group_sizes(n)
        assert all(6 <= s <= 8 for s in plan.sizes), n
        assert sum(plan.sizes) + plan.leftover == n, n
        assert max(plan.sizes, default=0) - min(plan.sizes, default=0) <= 1, n


def test_plan_group_sizes_targets_seven():
    assert len(plan_group_sizes(70).sizes) == 10
    assert len(plan_group_sizes(700).sizes) == 100


# ---- Rules 2 and 3: pools ---------------------------------------------------

def test_pools_are_keyed_by_category_and_language():
    df = concat(
        make_profiles(6, start=0),
        make_profiles(6, start=6, communication_language="Polish"),
        make_profiles(6, start=12, primary_condition_category="Respiratory",
                      primary_condition_subtype="COPD"),
    )
    pools, _ = partition_into_eligible_pools(df)
    assert set(pools) == {
        ("Cardiovascular", "English"),
        ("Cardiovascular", "Polish"),
        ("Respiratory", "English"),
    }
    for (cat, lang), pool in pools.items():
        assert (pool["primary_condition_category"] == cat).all()
        assert (pool["communication_language"] == lang).all()
    assert sum(len(p) for p in pools.values()) == len(df)


def test_small_pool_profiles_get_named_reason():
    df = concat(make_profiles(6, start=0),
                make_profiles(4, start=6, communication_language="Urdu"))
    _, audit = partition_into_eligible_pools(df)
    reasons = audit.excluded
    assert set(reasons) == {f"P{i:06d}" for i in range(6, 10)}
    assert reasons["P000006"] == (
        "pool_too_small: category=Cardiovascular, language=Urdu, "
        "pool_size=4, minimum_required=6"
    )


def test_pool_of_exactly_six_excludes_nobody():
    _, audit = partition_into_eligible_pools(make_profiles(6))
    assert audit.excluded == {}


def test_every_rule_is_logged_even_when_it_excludes_no_one():
    _, audit = partition_into_eligible_pools(make_profiles(7))
    rules = {entry["rule"]: entry for entry in audit.rules}
    assert rules["adult_eligibility"]["excluded"] == 0
    assert rules["adult_eligibility"]["checked"] == 7
    assert rules["shared_condition_category"]["excluded"] == 0
    assert rules["shared_communication_language"]["excluded"] == 0


def test_pool_summary_reports_size_and_viability():
    df = concat(make_profiles(7, start=0),
                make_profiles(3, start=7, communication_language="Urdu"))
    _, audit = partition_into_eligible_pools(df)
    summary = {(p["category"], p["language"]): p for p in audit.pools}
    assert summary[("Cardiovascular", "English")]["viable"] is True
    assert summary[("Cardiovascular", "Urdu")]["viable"] is False
    assert summary[("Cardiovascular", "Urdu")]["size"] == 3


def test_non_adult_band_is_rejected():
    df = make_profiles(7, age_band=["16-17"] + ["45-59"] * 6)
    pools, audit = partition_into_eligible_pools(df)
    assert audit.excluded["P000000"].startswith("not_adult")
    assert sum(len(p) for p in pools.values()) == 6
