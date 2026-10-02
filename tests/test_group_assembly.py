"""Group assembly: objective function, greedy construction,
local-swap refinement, and edge cases."""

import numpy as np
import pytest

from factories import make_profiles, concat
from matching.attributes import DEFAULT_WEIGHTS, equal_weights
from matching.similarity import compute_gower_distance_matrix
from matching.group_assembly import assemble_groups, score_group

W = DEFAULT_WEIGHTS
H_TOTAL = 1 - W["support_orientation"] - W["psychosocial_isolation_score"]  # 0.7609


def run(df, weights=W, **kw):
    return assemble_groups(df, compute_gower_distance_matrix(df, weights), weights, **kw)


def members(result):
    return [set(g) for g in result.groups]


# ---- Objective function ------------------------------------------------------

def test_score_hand_computed():
    # Identical on homogeneity (mean similarity 1), one of each orientation
    # (normalised entropy 1), all in one isolation band (entropy 0).
    df = make_profiles(3, support_orientation=["Seeking", "Balanced", "Offering"])
    d = compute_gower_distance_matrix(df, W)
    expected = H_TOTAL * 1.0 + W["support_orientation"] * 1.0 + W["psychosocial_isolation_score"] * 0.0
    assert score_group(df, d, W, [0, 1, 2]) == pytest.approx(expected, abs=1e-4)


def test_score_isolation_entropy_uses_four_trial_bands():
    # One member in each band: low, moderate, moderately high, high.
    df = make_profiles(4, psychosocial_isolation_score=[25.0, 40.0, 55.0, 70.0])
    d = compute_gower_distance_matrix(df, W)
    expected = H_TOTAL + W["psychosocial_isolation_score"] * 1.0
    assert score_group(df, d, W, [0, 1, 2, 3]) == pytest.approx(expected, abs=1e-4)


# ---- Edge cases ----------------------------------------------------------------

def test_empty_pool():
    result = run(make_profiles(0))
    assert result.groups == [] and result.unmatched == {}


def test_pool_below_minimum_forms_no_group_and_logs_everyone():
    result = run(make_profiles(5))
    assert result.groups == []
    assert len(result.unmatched) == 5
    assert all(r.startswith("pool_too_small") for r in result.unmatched.values())


def test_pool_exactly_at_minimum_forms_one_group():
    result = run(make_profiles(6))
    assert [len(g) for g in result.groups] == [6]
    assert result.unmatched == {}


def test_identical_profiles_do_not_crash_and_converge():
    result = run(make_profiles(14))
    assert sorted(len(g) for g in result.groups) == [7, 7]
    assert result.stopping == "converged"
    assert result.scores[0] == pytest.approx(result.scores[1])


def test_indivisible_remainder_is_logged_not_forced():
    result = run(make_profiles(17))
    assert [len(g) for g in result.groups] == [8, 8]
    assert len(result.unmatched) == 1
    reason = next(iter(result.unmatched.values()))
    assert reason.startswith("remainder_not_absorbable")


def test_every_profile_is_placed_exactly_once():
    df = make_profiles(50, age_band=(["18-29", "30-44", "45-59", "60-74", "75+"] * 10))
    result = run(df)
    placed = [p for g in result.groups for p in g] + list(result.unmatched)
    assert sorted(placed) == sorted(df["profile_id"])
    assert all(6 <= len(g) <= 8 for g in result.groups)


# ---- Behaviour -----------------------------------------------------------------

def test_recovers_planted_homogeneous_clusters():
    a = make_profiles(7, start=0, primary_condition_subtype="Heart failure",
                      primary_support_goal="emotional_support", age_band="75+")
    b = make_profiles(7, start=7, primary_condition_subtype="Stroke and TIA",
                      primary_support_goal="accountability", age_band="18-29")
    df = concat(a, b).sample(frac=1, random_state=3).reset_index(drop=True)
    result = run(df)
    assert sorted(members(result), key=min) == [set(a["profile_id"]), set(b["profile_id"])]


def test_complementarity_mixes_support_orientation():
    df = make_profiles(14, support_orientation=["Seeking"] * 7 + ["Offering"] * 7)
    result = run(df)
    lookup = dict(zip(df["profile_id"], df["support_orientation"]))
    for group in result.groups:
        assert {lookup[p] for p in group} == {"Seeking", "Offering"}


def test_local_swap_never_lowers_total_score():
    rng = np.random.default_rng(0)
    n = 40
    df = make_profiles(
        n,
        age_band=list(rng.choice(["18-29", "30-44", "45-59", "60-74", "75+"], n)),
        primary_support_goal=list(rng.choice(["emotional_support", "accountability",
                                              "shared_activity"], n)),
        support_orientation=list(rng.choice(["Seeking", "Balanced", "Offering"], n)),
        psychosocial_isolation_score=list(rng.uniform(20, 80, n)),
    )
    result = run(df)
    assert result.total_score_after_swaps >= result.total_score_after_greedy - 1e-12
    assert sum(result.scores) == pytest.approx(result.total_score_after_swaps)


def test_same_seed_same_groups():
    df = make_profiles(30, age_band=(["18-29", "75+", "45-59"] * 10))
    assert members(run(df, seed=1)) == members(run(df, seed=1))


def test_stopping_condition_is_logged_when_pass_limit_hit():
    df = make_profiles(30, age_band=(["18-29", "75+", "45-59"] * 10))
    result = run(df, max_passes=0)
    assert result.stopping == "max_passes_reached"


def test_equal_weights_run_through_the_same_procedure():
    df = make_profiles(14, age_band=["18-29"] * 7 + ["75+"] * 7)
    result = run(df, weights=equal_weights())
    assert sorted(len(g) for g in result.groups) == [7, 7]


def test_group_details_support_explanations():
    result = run(make_profiles(7, support_orientation=["Seeking"] * 4 + ["Offering"] * 3))
    detail = result.group_details[0]
    assert set(detail["homogeneity_similarity"]) == {
        "primary_condition_subtype", "primary_support_goal", "age_band",
        "condition_duration_band", "gender", "engagement_level"}
    assert set(detail["complementarity_entropy"]) == {
        "support_orientation", "psychosocial_isolation_score"}
    assert len(detail["weakest_link"]["pair"]) == 2


def test_vectorised_swap_deltas_match_brute_force():
    from matching.group_assembly import _swap_deltas, _score, complementarity_codes
    rng = np.random.default_rng(7)
    n = 21
    df = make_profiles(
        n,
        age_band=list(rng.choice(["18-29", "30-44", "45-59", "60-74", "75+"], n)),
        engagement_level=list(rng.choice(["Low", "Medium", "High"], n)),
        support_orientation=list(rng.choice(["Seeking", "Balanced", "Offering"], n)),
        psychosocial_isolation_score=list(rng.uniform(20, 80, n)),
    )
    d = compute_gower_distance_matrix(df, W)
    codes = complementarity_codes(df)
    labels = np.array([0] * 7 + [1] * 6 + [2] * 8)
    sizes = np.bincount(labels)
    delta = _swap_deltas(labels, 1.0 - d, sizes * (sizes - 1) / 2.0, codes, W)
    groups = [list(np.nonzero(labels == g)[0]) for g in range(3)]
    for a in range(n):
        for b in range(a + 1, n):
            ga, gb = labels[a], labels[b]
            if ga == gb:
                continue
            new_a = [b if x == a else x for x in groups[ga]]
            new_b = [a if x == b else x for x in groups[gb]]
            expected = (_score(new_a, d, codes, W) + _score(new_b, d, codes, W)
                        - _score(groups[ga], d, codes, W) - _score(groups[gb], d, codes, W))
            assert delta[a, b] == pytest.approx(expected, abs=1e-9), (a, b)
