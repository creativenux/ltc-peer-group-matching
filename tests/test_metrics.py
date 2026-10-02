"""Cohesion metrics: silhouette, within-group distance, cohesion index, unmatched rate."""

import math

import pytest

from factories import make_profiles, concat
from matching.attributes import DEFAULT_WEIGHTS
from matching.pipeline import run_all_methods
from evaluation.metrics import evaluate_run

H_TOTAL = sum(DEFAULT_WEIGHTS[a] for a in (
    "primary_condition_subtype", "primary_support_goal", "age_band",
    "condition_duration_band", "gender", "engagement_level"))


def two_clusters():
    a = make_profiles(7, start=0, primary_condition_subtype="Heart failure",
                      primary_support_goal="emotional_support", age_band="75+")
    b = make_profiles(7, start=7, primary_condition_subtype="Stroke and TIA",
                      primary_support_goal="accountability", age_band="18-29")
    return concat(a, b).sample(frac=1, random_state=1).reset_index(drop=True)


def test_perfectly_separated_groups_have_silhouette_one():
    metrics = evaluate_run(run_all_methods(two_clusters(), methods=["weighted_gower"]))
    assert metrics["weighted_gower"]["silhouette_weighted"] == pytest.approx(1.0)
    assert metrics["weighted_gower"]["within_group_distance"] == pytest.approx(0.0)


def test_cohesion_index_is_mean_score_under_the_default_weights_for_every_method():
    # Identical profiles, one orientation, one isolation band: Score(G) = H weights only.
    metrics = evaluate_run(run_all_methods(make_profiles(14)))
    for method, m in metrics.items():
        assert m["cohesion_index"] == pytest.approx(H_TOTAL), method


def test_unmatched_rate_counts_every_profile_that_was_not_grouped():
    df = concat(make_profiles(17, start=0),
                make_profiles(3, start=17, communication_language="Urdu"))
    metrics = evaluate_run(run_all_methods(df, methods=["random"]))
    assert metrics["random"]["unmatched_rate"] == pytest.approx(4 / 20)


def test_silhouette_is_undefined_when_no_pool_has_two_groups():
    metrics = evaluate_run(run_all_methods(make_profiles(7), methods=["random"]))
    assert math.isnan(metrics["random"]["silhouette_weighted"])


def test_per_attribute_within_group_dissimilarity_is_reported():
    metrics = evaluate_run(run_all_methods(two_clusters(), methods=["random"]))
    per_attribute = metrics["random"]["within_group_dissimilarity"]
    assert set(per_attribute) == {"primary_condition_subtype", "primary_support_goal", "age_band",
                                  "condition_duration_band", "gender", "engagement_level"}
    assert per_attribute["gender"] == 0.0
