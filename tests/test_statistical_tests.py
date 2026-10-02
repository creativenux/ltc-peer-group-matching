"""Friedman omnibus test, Kendall's W, Wilcoxon signed-rank with Holm
correction, matched-pairs rank-biserial correlation."""

import numpy as np
import pytest

from evaluation.statistical_tests import (
    holm_adjust, rank_biserial, kendalls_w, compare_methods,
)


def test_holm_adjustment_hand_computed():
    # sorted: .01*3 = .03; .03*2 = .06; .04*1 = .04 -> monotone max .06
    assert holm_adjust([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_holm_caps_at_one():
    assert holm_adjust([0.6, 0.7]) == pytest.approx([1.0, 1.0])


def test_rank_biserial_extremes_and_zero_differences():
    assert rank_biserial([2, 3, 4], [1, 1, 1]) == pytest.approx(1.0)
    assert rank_biserial([1, 1, 1], [2, 3, 4]) == pytest.approx(-1.0)
    # zero differences are dropped, as in the Wilcoxon test
    assert rank_biserial([1, 5], [1, 4]) == pytest.approx(1.0)


def test_kendalls_w_is_one_when_every_replicate_ranks_methods_the_same():
    table = {"a": [3, 3.1, 3.2, 3.3], "b": [2, 2.1, 2.2, 2.3], "c": [1, 1.1, 1.2, 1.3]}
    stat, p, w = kendalls_w(table)
    assert w == pytest.approx(1.0)


def test_compare_methods_reports_friedman_then_pairwise_against_reference():
    rng = np.random.default_rng(0)
    n = 20
    table = {
        "weighted_gower": list(0.9 + rng.normal(0, 0.01, n)),
        "random": list(0.6 + rng.normal(0, 0.01, n)),
        "single_age_band": list(0.7 + rng.normal(0, 0.01, n)),
    }
    out = compare_methods(table, reference="weighted_gower", higher_is_better=True)
    assert out["friedman"]["p_value"] < 0.001
    assert out["friedman"]["kendalls_w"] > 0.9
    pairs = {p["baseline"]: p for p in out["pairwise"]}
    assert set(pairs) == {"random", "single_age_band"}
    for p in pairs.values():
        assert p["p_holm"] < 0.001
        assert p["rank_biserial"] == pytest.approx(1.0)
        assert "better" in p["interpretation"]


def test_identical_methods_are_reported_not_tested():
    table = {"weighted_gower": [0.1] * 5, "random": [0.1] * 5, "single_age_band": [0.1] * 5}
    out = compare_methods(table, reference="weighted_gower", higher_is_better=False)
    assert out["friedman"] is None
    assert out["pairwise"] == []
    assert "identical" in out["note"]


def test_methods_equal_within_every_replicate_are_not_tested_even_if_replicates_vary():
    per_replicate = [0.01, 0.02, 0.015, 0.03]
    table = {"weighted_gower": per_replicate, "random": per_replicate,
             "single_age_band": per_replicate}
    out = compare_methods(table, reference="weighted_gower", higher_is_better=False)
    assert out["friedman"] is None
    assert "identical" in out["note"]
