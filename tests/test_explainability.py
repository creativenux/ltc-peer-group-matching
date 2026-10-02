"""Explainability layer: plain-language group summaries and unmatched reasons."""

from factories import make_profiles
from matching.attributes import DEFAULT_WEIGHTS
from matching.similarity import compute_gower_distance_matrix
from matching.group_assembly import assemble_groups
from matching.explainability import explain_group, explain_unmatched


def one_group(**overrides):
    df = make_profiles(7, **overrides)
    result = assemble_groups(df, compute_gower_distance_matrix(df, DEFAULT_WEIGHTS), DEFAULT_WEIGHTS)
    return result.group_details[0]


def test_summary_names_the_two_strongest_attributes_breaking_ties_by_weight():
    # Everything identical: all six similarities are 1, so the two highest
    # weights (condition sub-type, support goal) are named.
    text = explain_group(one_group())
    assert text["strongest_attributes"] == ["primary_condition_subtype", "primary_support_goal"]
    assert "condition sub-type" in text["summary"] and "support goal" in text["summary"]


def test_summary_prefers_the_attribute_members_actually_share():
    ages = ["18-29", "30-44", "45-59", "60-74", "75+", "18-29", "75+"]
    goals = ["emotional_support", "accountability", "shared_activity", "social_connection",
             "self_management_info", "accountability", "shared_activity"]
    text = explain_group(one_group(age_band=ages, primary_support_goal=goals))
    assert "primary_support_goal" not in text["strongest_attributes"]
    assert "age_band" not in text["strongest_attributes"]


def test_weakest_link_is_named_by_profile_id():
    detail = one_group(age_band=["18-29"] + ["45-59"] * 5 + ["75+"])
    text = explain_group(detail)
    assert "P000000" in text["weakest_link"] and "P000006" in text["weakest_link"]


def test_balance_wording():
    balanced = explain_group(one_group(support_orientation=["Seeking", "Balanced", "Offering"] * 2 + ["Seeking"]))
    dominated = explain_group(one_group(support_orientation="Seeking"))
    assert balanced["balance"]["support_orientation"] == "well balanced across support orientation"
    assert dominated["balance"]["support_orientation"] == (
        "dominated by one support orientation (all Seeking)")


def test_unmatched_reasons_in_plain_language():
    assert explain_unmatched(
        "pool_too_small: category=Cardiovascular, language=Urdu, pool_size=4, minimum_required=6"
    ) == ("Not grouped: only 4 people share the Cardiovascular condition category and the "
          "Urdu language, and a group needs at least 6.")
    assert explain_unmatched(
        "remainder_not_absorbable: pool_size=17 cannot be divided into groups of 6 to 8; 1 left over"
    ).startswith("Not grouped: a pool of 17 people cannot be split into groups of 6 to 8")
    assert explain_unmatched("not_adult: age_band=16-17, minimum_age=18").startswith(
        "Not eligible: age band 16-17")
