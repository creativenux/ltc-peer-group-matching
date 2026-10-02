"""Weight sensitivity: +/-10% perturbation with proportional redistribution,
compared to the original grouping by Adjusted Rand Index."""

import pytest

from data_generation import generate_dataset
from matching.attributes import DEFAULT_WEIGHTS
from evaluation.sensitivity import set_weight, perturb_weight, grouping_ari, run_sensitivity


def test_perturbation_scales_one_weight_and_keeps_the_sum_at_one():
    w = perturb_weight(DEFAULT_WEIGHTS, "age_band", +0.10)
    assert w["age_band"] == pytest.approx(DEFAULT_WEIGHTS["age_band"] * 1.1)
    assert sum(w.values()) == pytest.approx(1.0)
    # the other seven keep their relative proportions
    ratio = w["gender"] / w["engagement_level"]
    assert ratio == pytest.approx(DEFAULT_WEIGHTS["gender"] / DEFAULT_WEIGHTS["engagement_level"])


def test_weight_to_zero_and_back_without_division_error():
    zero = set_weight(DEFAULT_WEIGHTS, "gender", 0.0)
    assert zero["gender"] == 0.0 and sum(zero.values()) == pytest.approx(1.0)
    back = set_weight(zero, "gender", DEFAULT_WEIGHTS["gender"])
    direct = set_weight(DEFAULT_WEIGHTS, "gender", DEFAULT_WEIGHTS["gender"])
    for a in DEFAULT_WEIGHTS:
        assert back[a] == pytest.approx(direct[a], abs=1e-12)


def test_weight_taking_everything_and_back():
    alone = set_weight(DEFAULT_WEIGHTS, "gender", 1.0)
    back = set_weight(alone, "gender", 0.5)
    assert sum(back.values()) == pytest.approx(1.0)
    assert all(v > 0 for v in back.values())


def test_identical_groupings_have_ari_one():
    groups = [["a", "b", "c"], ["d", "e", "f"]]
    assert grouping_ari(groups, [["f", "e", "d"], ["c", "a", "b"]]) == pytest.approx(1.0)


def test_sensitivity_covers_every_attribute_in_both_directions():
    report = run_sensitivity(generate_dataset(300, seed=4), seed=4)
    rows = report["perturbations"]
    assert len(rows) == 16
    assert {r["attribute"] for r in rows} == set(DEFAULT_WEIGHTS)
    assert all(-1.0 <= r["ari"] <= 1.0 for r in rows)
    assert [r["attribute"] for r in report["ranking"]][0] in DEFAULT_WEIGHTS
    assert -1.0 <= report["seed_reference_ari"] <= 1.0


def test_sensitivity_reports_group_quality_under_the_default_weights():
    report = run_sensitivity(generate_dataset(300, seed=4), seed=4)
    assert 0.0 <= report["base_within_group_distance"] <= 1.0
    assert 0.0 <= report["seed_reference_within_group_distance"] <= 1.0
    assert all(0.0 <= r["within_group_distance"] <= 1.0 for r in report["perturbations"])
