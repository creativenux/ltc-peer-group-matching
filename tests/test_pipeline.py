"""End-to-end: hard rules -> every method on every pool."""

from data_generation import generate_dataset
from matching.pipeline import METHODS, run_all_methods


def test_every_method_accounts_for_every_profile_exactly_once():
    df = generate_dataset(400, seed=5)
    run = run_all_methods(df, seed=5)
    assert set(run.methods) == set(METHODS) == {
        "weighted_gower", "unweighted_gower", "single_age_band",
        "single_primary_support_goal", "random"}
    for method, outcome in run.methods.items():
        placed = [p for g in outcome.groups for p in g] + list(outcome.unmatched)
        assert sorted(placed) == sorted(df["profile_id"]), method
        assert all(6 <= len(g) <= 8 for g in outcome.groups), method


def test_group_counts_are_identical_across_methods():
    run = run_all_methods(generate_dataset(400, seed=6), seed=6)
    counts = {m: len(o.groups) for m, o in run.methods.items()}
    assert len(set(counts.values())) == 1, counts


def test_groups_never_cross_pools():
    df = generate_dataset(400, seed=7)
    run = run_all_methods(df, seed=7)
    key = {p: (c, l) for p, c, l in zip(df["profile_id"], df["primary_condition_category"],
                                          df["communication_language"])}
    for outcome in run.methods.values():
        for g in outcome.groups:
            assert len({key[p] for p in g}) == 1
