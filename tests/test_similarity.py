"""Weighted Gower distance, checked against hand-computed values."""

import numpy as np
import pytest

from factories import make_profiles
from matching.attributes import DEFAULT_WEIGHTS, homogeneity_weights
from matching.similarity import (
    gower_distance_matrix,
    compute_gower_distance_matrix,
    compute_unweighted_gower_distance_matrix,
)

W = DEFAULT_WEIGHTS
H_TOTAL = (W["primary_condition_subtype"] + W["primary_support_goal"] + W["age_band"]
           + W["condition_duration_band"] + W["gender"] + W["engagement_level"])  # 0.7608


def test_nominal_mismatch_contributes_its_weight_share():
    df = make_profiles(2, primary_condition_subtype=["Heart failure", "Stroke and TIA"])
    d = compute_gower_distance_matrix(df, W)
    assert d[0, 1] == pytest.approx(0.2174 / H_TOTAL)          # 0.28575


def test_ordinal_distance_is_rank_gap_over_range():
    df = make_profiles(3, age_band=["18-29", "75+", "60-74"])
    d = compute_gower_distance_matrix(df, W)
    # 18-29 -> 75+ is the full 4-step range; 75+ -> 60-74 is 1 of 4 steps.
    assert d[0, 1] == pytest.approx(0.1304 * 1.0 / H_TOTAL)
    assert d[1, 2] == pytest.approx(0.1304 * 0.25 / H_TOTAL)


def test_numeric_distance_uses_pool_range():
    df = make_profiles(3, psychosocial_isolation_score=[20.0, 50.0, 80.0])
    d = gower_distance_matrix(df, {"psychosocial_isolation_score": 1.0})
    assert d[0, 1] == pytest.approx(30 / 60)
    assert d[0, 2] == pytest.approx(1.0)


def test_numeric_zero_range_gives_zero_not_nan():
    df = make_profiles(3, psychosocial_isolation_score=40.0)
    d = gower_distance_matrix(df, {"psychosocial_isolation_score": 1.0})
    assert np.all(d == 0)


def test_mixed_hand_computed_pair():
    df = make_profiles(2,
                       primary_condition_subtype=["Heart failure", "Atrial fibrillation"],
                       condition_duration_band=["3-5", "11-20"],   # ranks 2 and 4 of 0..5
                       engagement_level=["Low", "High"])           # full range
    expected = (0.2174 * 1 + 0.1087 * (2 / 5) + 0.0543 * 1) / H_TOTAL
    assert compute_gower_distance_matrix(df, W)[0, 1] == pytest.approx(expected)


def test_complementarity_attributes_are_excluded_from_pairwise_distance():
    df = make_profiles(2, support_orientation=["Seeking", "Offering"],
                       psychosocial_isolation_score=[20.0, 80.0])
    assert compute_gower_distance_matrix(df, W)[0, 1] == 0.0


def test_unweighted_gives_each_homogeneity_attribute_one_sixth():
    df = make_profiles(2, primary_condition_subtype=["Heart failure", "Stroke and TIA"])
    assert compute_unweighted_gower_distance_matrix(df)[0, 1] == pytest.approx(1 / 6)


def test_matrix_is_symmetric_zero_diagonal_and_bounded():
    df = make_profiles(5,
                       age_band=["18-29", "30-44", "45-59", "60-74", "75+"],
                       gender=["Woman", "Man", "Woman", "Non-binary or self-describe", "Man"],
                       primary_support_goal=["emotional_support", "accountability",
                                             "shared_activity", "emotional_support",
                                             "social_connection"])
    d = compute_gower_distance_matrix(df, W)
    assert d.shape == (5, 5)
    assert np.allclose(d, d.T)
    assert np.all(np.diag(d) == 0)
    assert d.min() >= 0 and d.max() <= 1


def test_homogeneity_weights_renormalise_to_one():
    hw = homogeneity_weights(W)
    assert set(hw) == {"primary_condition_subtype", "primary_support_goal", "age_band",
                       "condition_duration_band", "gender", "engagement_level"}
    assert sum(hw.values()) == pytest.approx(1.0)
