"""
schema.py

Attribute schema, condition list and calibration constants for the synthetic
dataset. Each constant has a comment giving its source. No generation logic
lives here (see data_generation.py).
"""

from __future__ import annotations

# =============================================================================
# CONFIG: demographic, condition, and matching-attribute distributions.
# =============================================================================

CONFIG = {

    # ---- Age band --------------------------------------------------------
    # Age is stored as a band only, never a real age, so no value can be tied
    # to a person (agreed with supervisor). Weights are older than the
    # national population because everyone has an LTC, following the
    # multimorbidity/age gradient in Barnett et al. (2012, Table 1) and
    # Valabhji et al. (2024).
    "age_band_weights": {
        "18-29": 0.05,
        "30-44": 0.12,
        "45-59": 0.25,
        "60-74": 0.33,
        "75+":   0.25,
    },
    # Upper age per band, used only to gate which conditions are plausible.
    "age_band_upper": {"18-29": 29, "30-44": 44, "45-59": 59, "60-74": 74, "75+": 95},
    # Adult-years available in a band, used to cap the duration band.
    "age_band_adult_years_upper": {"18-29": 11, "30-44": 26, "45-59": 41, "60-74": 56, "75+": 77},

    # ---- Gender (soft matching attribute) ---------------------------------
    # Women had higher multimorbidity than men (26.2% vs 20.1%; Barnett et
    # al., 2012, Table 1), so women are modestly over-represented. Non-binary
    # / self-describe share follows the ~0.5% reporting a gender identity
    # different from sex registered at birth (ONS, 2023, Census 2021 gender
    # identity outputs).
    "gender": {"Woman": 0.520, "Man": 0.475, "Non-binary or self-describe": 0.005},

    # ---- Communication language (hard-rule attribute) ---------------------
    # Census 2021 main-language shares for England (Office for National
    # Statistics, 2022). "Other" absorbs all remaining main languages.
    "language": {
        "English": 0.908,
        "Polish": 0.011,
        "Romanian": 0.009,
        "Panjabi": 0.005,
        "Urdu": 0.005,
        "Other": 0.062,
    },

    # ---- Deprivation (IMD quintile; only used to drive the isolation score) -
    "imd_quintiles": [1, 2, 3, 4, 5],  # 1 = most deprived, 5 = least deprived; sampled uniformly

    # ---- Living alone (feeds isolation) ------------------------------------
    # Anchored to Census 2021: 8.5% of people aged 16-49 live alone (ONS,
    # 2023, "People's living arrangements in England and Wales"), rising
    # steeply with age (one-person households concentrated at 66+; ONS,
    # 2022, "Household and resident characteristics"). The by-band rates
    # are interpolated between these two anchors.
    "lives_alone_prob_by_band": {
        "18-29": 0.08, "30-44": 0.11, "45-59": 0.16, "60-74": 0.28, "75+": 0.45,
    },

    # ---- Multimorbidity -----------------------------------------------------
    # Grounded in Barnett et al. (2012, Table 1): of people with >=1 of the 40
    # morbidities, 54.9% were multimorbid, rising from 11.3% (25-44) to 30.4%
    # (45-64), 64.9% (65-84), 81.5% (85+). By-band values below follow this
    # gradient, mapped onto the project's age bands.
    "multimorbid_share_by_band": {
        "18-29": 0.30, "30-44": 0.38, "45-59": 0.50, "60-74": 0.62, "75+": 0.70,
    },
    # Deprivation modestly raises multimorbidity (19.5% vs 24.1% crude,
    # affluent vs deprived deciles; Barnett et al., 2012, Table 1).
    "multimorbid_imd_adjust": {1: 0.05, 2: 0.03, 3: 0.00, 4: -0.02, 5: -0.04},
    # Distribution of total condition count GIVEN multimorbid, derived from
    # the whole-population count distribution in Barnett et al. (2012, Table
    # 1: patients with 2, 3, 4, 5, 6+ disorders, renormalised over >=2).
    "multimorbid_count_dist": {2: 0.414, 3: 0.246, 4: 0.148, 5: 0.086, 6: 0.106},
    # The odds of a mental-health disorder rise steeply with the number of
    # physical conditions (adjusted OR 1.95 at 1 physical disorder up to 6.74
    # at 5+; Barnett et al., 2012, Table 2). Used as a multiplier that makes
    # anxiety/depression more likely as a comorbidity as condition count grows.
    "mental_health_boost_per_condition": 1.6,

    # ---- Support and engagement attributes (ASSUMPTION: no population data
    # exists for a peer-support service; agreed with supervisor, 1 July 2026) -
    "primary_support_goal": {
        "emotional_support": 0.26,
        "self_management_info": 0.22,
        "social_connection": 0.22,
        "accountability": 0.15,
        "shared_activity": 0.15,
    },
    "support_orientation": {"Seeking": 0.40, "Balanced": 0.40, "Offering": 0.20},
    "engagement_level": {"Low": 0.25, "Medium": 0.50, "High": 0.25},

    # ---- Isolation score (UCLA-derived, revised scale range 20-80) --------
    # Construct based on the UCLA Loneliness Scale, Version 3 (Russell,
    # 1996), score range 20-80. Synthetic value; never administered. Higher
    # burden and living alone raise isolation, consistent with the health
    # gradient in loneliness (49% lonely at least sometimes among adults in
    # bad/very bad health vs 17% in good/very good health; NHS England,
    # 2026 Health Survey for England) and with the mortality risk of living
    # alone (Holt-Lunstad et al., 2015).
    "isolation_base_mean": 42.0,
    "isolation_base_sd": 10.0,
    "isolation_per_extra_condition": 2.5,
    "isolation_lives_alone": 6.0,
    # Isolation falls as deprivation decreases (quintile 5 = least deprived),
    # consistent with the loneliness-by-deprivation gradient (17% to 28%
    # lonely at least sometimes, least to most deprived quintile; NHS
    # England, 2026).
    "isolation_imd_effect": {1: 5.0, 2: 2.5, 3: 0.0, 4: -2.0, 5: -4.0},
    # Categorisation used in loneliness intervention trials (e.g. Baltimore
    # HEARS trial, ClinicalTrials.gov NCT03442296): 20-34 low, 35-49
    # moderate, 50-64 moderately high, 65-80 high. Threshold set at 50
    # (moderately high and above counts as "high isolation" for reporting).
    "isolation_high_threshold": 50.0,
}


# =============================================================================
# CONDITION TAXONOMY
# Verified against Payne et al. (2020, Table 2): the 20-condition Cambridge
# Multimorbidity Score, developed and validated on UK primary care data
# (CPRD). Curated down to chronic conditions with a documented association
# with loneliness or social isolation (National Academies of Sciences,
# Engineering, and Medicine, 2020) that also form a meaningful basis for a
# peer support group. Hearing loss, vision loss, and largely-asymptomatic
# hypertension are excluded by project direction; dementia, psychosis/
# bipolar disorder, and alcohol problems are excluded because they raise
# capacity, consent, or distinct safeguarding considerations outside the
# scope of a self-directed peer group.
# =============================================================================

# Parent category -> curated Cambridge Multimorbidity Score sub-types.
PARENT_CATEGORIES = {
    "Cardiovascular": [
        "Coronary heart disease", "Heart failure", "Stroke and TIA",
        "Atrial fibrillation",
    ],
    "Metabolic and endocrine": ["Diabetes mellitus"],
    "Respiratory": ["COPD"],
    "Mental health": ["Anxiety or depression"],
    "Musculoskeletal and chronic pain": ["Painful condition", "Connective tissue disorder"],
    "Renal": ["Chronic kidney disease"],
    "Cancer experience": ["Cancer"],
}

# Whole-population primary-care prevalence (%) from Payne et al. (2020,
# Table 2), used as the relative sampling weight for condition selection.
# These are whole-population, not LTC-population, prevalences; conditioning
# on "has >=1 LTC" divides every condition's prevalence by a broadly similar
# factor, so relative weights among conditions are not materially distorted
# by using the whole-population figures directly (agreed with supervisor,
# 1 July 2026 call, in place of an LTC-specific breakdown, which is not
# published for this condition set).
CONDITION_WEIGHTS = {
    "Anxiety or depression": 12.85,
    "Painful condition": 11.63,
    "Diabetes mellitus": 6.58,
    "Coronary heart disease": 4.79,
    "Chronic kidney disease": 4.50,
    "Atrial fibrillation": 2.72,
    "Stroke and TIA": 2.55,
    "COPD": 2.46,
    "Connective tissue disorder": 2.33,
    "Cancer": 2.15,
    "Heart failure": 1.04,
}

# Minimum plausible onset age per condition, used only as a band-eligibility
# gate (no real age is generated, so this stops late-onset conditions
# appearing in young bands, e.g. heart failure in 18-29). Clinical judgement.
MIN_ONSET_AGE = {
    "Anxiety or depression": 18,
    "Painful condition": 18,
    "Diabetes mellitus": 18,
    "Coronary heart disease": 35,
    "Chronic kidney disease": 30,
    "Atrial fibrillation": 40,
    "Stroke and TIA": 40,
    "COPD": 40,
    "Connective tissue disorder": 20,
    "Cancer": 25,
    "Heart failure": 45,
}

# Co-occurrence bias: if the primary condition is in one of these categories,
# comorbidities are twice as likely to come from the paired categories. A
# simplification of real co-occurrence patterns.
COOCCURRENCE_BIAS = {
    "Metabolic and endocrine": ["Cardiovascular"],
    "Cardiovascular": ["Metabolic and endocrine", "Renal"],
}

SUBTYPE_TO_PARENT = {
    sub: parent for parent, subs in PARENT_CATEGORIES.items() for sub in subs
}
ALL_SUBTYPES = list(SUBTYPE_TO_PARENT.keys())

# Ordinal duration bands (years lived with the primary condition) and the
# minimum number of years each band represents, used to cap duration by the
# adult years available in the profile's age band.
DURATION_BANDS = ["<1", "1-2", "3-5", "6-10", "11-20", "20+"]
DURATION_BAND_MIN_YEARS = {"<1": 0, "1-2": 1, "3-5": 3, "6-10": 6, "11-20": 11, "20+": 20}
