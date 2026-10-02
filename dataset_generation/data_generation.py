"""
data_generation.py

Generates synthetic profiles from the constants in schema.py and checks that
each profile is logically possible:

  - the duration band fits the adult years in the age band
  - the condition sub-type belongs to its category
  - no condition appears in an age band younger than its minimum onset age
  - comorbidities are distinct and do not repeat the primary condition
  - every profile has the fields the hard rules need

Age is stored as a band only. No real age, ethnicity or region is generated.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from schema import (
    CONFIG,
    CONDITION_WEIGHTS,
    MIN_ONSET_AGE,
    COOCCURRENCE_BIAS,
    SUBTYPE_TO_PARENT,
    ALL_SUBTYPES,
    DURATION_BANDS,
    DURATION_BAND_MIN_YEARS,
)


# =============================================================================
# SAMPLING HELPERS
# =============================================================================

def weighted_choice(rng: np.random.Generator, mapping: dict):
    """Choose a key from {key: weight} using the weights (normalised)."""
    keys = list(mapping.keys())
    weights = np.array([mapping[k] for k in keys], dtype=float)
    weights = weights / weights.sum()
    return keys[int(rng.choice(len(keys), p=weights))]


def allowed_subtypes_for_band(age_band: str) -> list:
    """Sub-types whose minimum plausible onset age fits within the band."""
    upper = CONFIG["age_band_upper"][age_band]
    return [s for s in ALL_SUBTYPES if MIN_ONSET_AGE.get(s, 0) <= upper]


def allowed_duration_bands(age_band: str) -> list:
    """Duration bands whose minimum years fit inside the adult years available."""
    cap = CONFIG["age_band_adult_years_upper"][age_band]
    return [b for b in DURATION_BANDS if DURATION_BAND_MIN_YEARS[b] <= cap]


# =============================================================================
# PROFILE GENERATION
# =============================================================================

def generate_profile(rng: np.random.Generator, index: int) -> dict:
    """Generate one internally consistent synthetic profile."""

    # 1. Age band
    age_band = weighted_choice(rng, CONFIG["age_band_weights"])

    # 2. Gender (soft matching attribute)
    gender = weighted_choice(rng, CONFIG["gender"])

    # 3. Deprivation quintile (drives the isolation score) and language
    imd_quintile = int(rng.choice(CONFIG["imd_quintiles"]))
    language = weighted_choice(rng, CONFIG["language"])

    # 4. Living situation (feeds isolation)
    lives_alone = rng.random() < CONFIG["lives_alone_prob_by_band"][age_band]

    # 5. Multimorbidity: decide multimorbid, then total condition count
    p_multi = CONFIG["multimorbid_share_by_band"][age_band] + \
        CONFIG["multimorbid_imd_adjust"][imd_quintile]
    p_multi = float(np.clip(p_multi, 0.0, 0.95))
    if rng.random() < p_multi:
        target_count = int(weighted_choice(rng, CONFIG["multimorbid_count_dist"]))
    else:
        target_count = 1

    # 6. Primary condition: plausible for the band, weighted by CMS prevalence
    allowed = allowed_subtypes_for_band(age_band)
    if not allowed:
        allowed = ["Anxiety or depression"]  # safety net; always plausible from 18-29
    primary_weights = {s: CONDITION_WEIGHTS.get(s, 1.0) for s in allowed}
    primary_subtype = weighted_choice(rng, primary_weights)
    primary_category = SUBTYPE_TO_PARENT[primary_subtype]

    # 7. Comorbidities: distinct, band-plausible, with co-occurrence bias and
    #    the physical-count to mental-health gradient (Barnett et al., 2012).
    comorbidities: list[str] = []
    pool = [s for s in allowed if s != primary_subtype]
    n_extra = min(target_count - 1, len(pool))
    if n_extra > 0:
        biased_parents = COOCCURRENCE_BIAS.get(primary_category, [])
        weights = {}
        for s in pool:
            w = CONDITION_WEIGHTS.get(s, 1.0)
            if SUBTYPE_TO_PARENT[s] in biased_parents:
                w *= 2.0
            if s == "Anxiety or depression":
                w *= CONFIG["mental_health_boost_per_condition"] * target_count
            weights[s] = w
        keys = list(weights.keys())
        probs = np.array([weights[k] for k in keys], dtype=float)
        probs = probs / probs.sum()
        chosen_idx = rng.choice(len(keys), size=n_extra, replace=False, p=probs)
        comorbidities = [keys[i] for i in chosen_idx]
    condition_count = 1 + len(comorbidities)

    # 8. Duration band of the primary condition, capped by adult years in the band
    condition_duration_band = weighted_choice(
        rng, {b: 1.0 for b in allowed_duration_bands(age_band)}
    )

    # 9. Support and matching attributes (assumptions; see schema.py)
    primary_support_goal = weighted_choice(rng, CONFIG["primary_support_goal"])
    support_orientation = weighted_choice(rng, CONFIG["support_orientation"])
    engagement_level = weighted_choice(rng, CONFIG["engagement_level"])

    # 10. Isolation score (UCLA-derived, 20-80), conditioned on burden
    score = rng.normal(CONFIG["isolation_base_mean"], CONFIG["isolation_base_sd"])
    score += CONFIG["isolation_per_extra_condition"] * (condition_count - 1)
    score += CONFIG["isolation_lives_alone"] if lives_alone else 0.0
    score += CONFIG["isolation_imd_effect"][imd_quintile]
    psychosocial_isolation_score = float(np.clip(round(score, 1), 20.0, 80.0))

    return {
        "profile_id": f"P{index:06d}",
        "age_band": age_band,
        "gender": gender,
        "imd_quintile": imd_quintile,
        "communication_language": language,
        "lives_alone": lives_alone,
        "primary_condition_category": primary_category,
        "primary_condition_subtype": primary_subtype,
        "condition_count": condition_count,
        "comorbidities": ";".join(comorbidities),  # semicolon-joined for CSV safety
        "condition_duration_band": condition_duration_band,
        "primary_support_goal": primary_support_goal,
        "support_orientation": support_orientation,
        "psychosocial_isolation_score": psychosocial_isolation_score,
        "engagement_level": engagement_level,
    }


def generate_dataset(n: int, seed: int) -> pd.DataFrame:
    """Generate a dataset of n profiles with a fixed seed (reproducible)."""
    rng = np.random.default_rng(seed)
    rows = [generate_profile(rng, i) for i in range(n)]
    return pd.DataFrame(rows)


# =============================================================================
# CONSISTENCY AUDIT
# Every count below should be zero; a non-zero count means a generation bug.
# =============================================================================

def audit_consistency(df: pd.DataFrame) -> dict:
    violations = {}

    valid_bands = set(CONFIG["age_band_weights"].keys())
    violations["invalid_age_band"] = int((~df["age_band"].isin(valid_bands)).sum())

    def dur_ok(row):
        return row["condition_duration_band"] in allowed_duration_bands(row["age_band"])
    violations["duration_exceeds_band"] = int((~df.apply(dur_ok, axis=1)).sum())

    def subtype_ok(row):
        return SUBTYPE_TO_PARENT.get(row["primary_condition_subtype"]) == \
            row["primary_condition_category"]
    violations["subtype_parent_mismatch"] = int((~df.apply(subtype_ok, axis=1)).sum())

    def onset_ok(row):
        return CONFIG["age_band_upper"][row["age_band"]] >= \
            MIN_ONSET_AGE.get(row["primary_condition_subtype"], 0)
    violations["condition_implausible_for_band"] = int((~df.apply(onset_ok, axis=1)).sum())

    def comorbid_ok(row):
        comps = [c for c in str(row["comorbidities"]).split(";") if c]
        if len(comps) != row["condition_count"] - 1:
            return False
        if row["primary_condition_subtype"] in comps:
            return False
        if len(set(comps)) != len(comps):
            return False
        return True
    violations["comorbidity_incoherent"] = int((~df.apply(comorbid_ok, axis=1)).sum())

    violations["isolation_out_of_range"] = int(
        ((df["psychosocial_isolation_score"] < 20) |
         (df["psychosocial_isolation_score"] > 80)).sum()
    )

    required = ["age_band", "primary_condition_category", "communication_language"]
    violations["missing_hard_rule_fields"] = int(df[required].isna().any(axis=1).sum())

    violations["TOTAL"] = int(sum(v for k, v in violations.items() if k != "TOTAL"))
    return violations
