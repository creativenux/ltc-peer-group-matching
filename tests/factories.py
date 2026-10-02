"""Test helpers: build small, fully specified profile DataFrames."""

import pandas as pd

BASE_PROFILE = {
    "age_band": "45-59",
    "gender": "Woman",
    "imd_quintile": 3,
    "communication_language": "English",
    "lives_alone": False,
    "primary_condition_category": "Cardiovascular",
    "primary_condition_subtype": "Heart failure",
    "condition_count": 1,
    "comorbidities": "",
    "condition_duration_band": "3-5",
    "primary_support_goal": "emotional_support",
    "support_orientation": "Balanced",
    "psychosocial_isolation_score": 40.0,
    "engagement_level": "Medium",
}


def make_profiles(n: int, start: int = 0, **overrides) -> pd.DataFrame:
    """n identical profiles (unless overridden), ids P{start}..P{start+n-1}.
    An override may be a scalar or a list of length n."""
    rows = []
    for i in range(n):
        row = {"profile_id": f"P{start + i:06d}", **BASE_PROFILE}
        for key, value in overrides.items():
            row[key] = value[i] if isinstance(value, list) else value
        rows.append(row)
    return pd.DataFrame(rows, columns=["profile_id", *BASE_PROFILE])


def concat(*frames) -> pd.DataFrame:
    return pd.concat(frames, ignore_index=True)
