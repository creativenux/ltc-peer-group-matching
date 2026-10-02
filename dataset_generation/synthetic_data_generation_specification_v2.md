# Synthetic Dataset Generation Specification

## 1. Purpose

This document describes how the synthetic dataset is designed, generated and validated. Together with the code in this folder, it is enough to reproduce the dataset.

Every calibration figure comes from a named source. Where no source exists, the figure is marked as an assumption.

## 2. Scope

The dataset is used to test a rules-based method that forms peer support groups of six to eight people living with a long-term condition (LTC). It represents adults in England.

The project does not use:
- human participants
- real or online patient data
- machine-learned or trained models

Design principles:
- every distribution is sourced or stated as an assumption
- every profile must be logically possible
- the data only needs to be realistic enough to test the matching method and the statistics, not to copy every feature of the real population

## 3. Design decisions

**Age.** Age is stored as a band (18-29, 30-44, 45-59, 60-74, 75+), never as a real age, so no value can be tied to a person.

**Removed attributes.** Ethnicity, region, a real integer age, communication modality and a safeguarding flag were removed. None of them is used for matching, and a randomly generated safeguarding flag would not be meaningful.

**Gender** is kept because it is a soft matching attribute.

**Deprivation (IMD quintile)** is kept only to drive the isolation score. It is not a matching attribute.

**Dataset size.** The generator is calibrated to national figures: about 14 million people in England live with multiple long-term conditions (Valabhji et al., 2024). Generation is fast (about 50,000 profiles in 20 seconds), but matching compares every pair of profiles, so its cost grows with the square of the number of profiles (Schubert & Rousseeuw, 2021). The project therefore uses:
- one dataset of 50,000 profiles (seed 42) to validate the generator
- 20 datasets of 3,000 profiles (seeds 42 to 61) for the matching evaluation

At 3,000 profiles the largest group of people who can be matched together has about 730 people, which keeps matching fast.

**Condition prevalence.** Conditions are weighted by their whole-population prevalence from Payne et al. (2020). No source gives prevalence within an LTC-only population for this condition list. Because every condition is affected in a similar way, the whole-population figures keep the right order between conditions. This is stated as a limitation.

**Minimum onset age.** Each condition has a minimum onset age, used to stop conditions appearing in age bands that are too young (for example, heart failure in 18-29).

**Support goal, support orientation and engagement level** have no population data. Their weights are assumptions agreed with the supervisor.

**Isolation score.** A synthetic score on the 20 to 80 range of the UCLA Loneliness Scale, Version 3 (Russell, 1996). It rises with the number of conditions, with living alone and with deprivation (Holt-Lunstad et al., 2015; NHS England, 2026).

## 4. Condition list

The condition list comes from the Cambridge Multimorbidity Score (Payne et al., 2020), which was developed on UK primary care data. It was reduced to conditions linked to loneliness or social isolation (National Academies of Sciences, Engineering, and Medicine, 2020) that are a sensible basis for a peer support group.

| Category | Conditions | Prevalence (%) |
|---|---|---|
| Cardiovascular | Coronary heart disease, Heart failure, Stroke and TIA, Atrial fibrillation | 4.79, 1.04, 2.55, 2.72 |
| Metabolic and endocrine | Diabetes mellitus | 6.58 |
| Respiratory | COPD | 2.46 |
| Mental health | Anxiety or depression | 12.85 |
| Musculoskeletal and chronic pain | Painful condition, Connective tissue disorder | 11.63, 2.33 |
| Renal | Chronic kidney disease | 4.50 |
| Cancer experience | Cancer | 2.15 |

Prevalences are from Payne et al. (2020, Table 2).

Excluded conditions:
- hearing loss and vision loss: sensory, not a basis for a peer group
- hypertension: usually without symptoms
- constipation and irritable bowel syndrome: weak evidence of isolation
- dementia: raises capacity and consent issues
- psychosis, bipolar disorder and alcohol problems: need specialist support
- epilepsy: left out to keep the list short

Barnett et al. (2012), a study of 1.75 million people in Scotland, is used for the pattern of multimorbidity: how it rises with age and deprivation, how many conditions people have, and how mental health conditions become more likely as physical conditions increase.

## 5. Profile attributes

| Attribute | Use | Type | Values | Source |
|---|---|---|---|---|
| `profile_id` | Unique key | Text | P000000, P000001, ... | |
| `age_band` | Matching; limits which conditions are possible | Ordinal | 18-29, 30-44, 45-59, 60-74, 75+ | Barnett et al. (2012); Valabhji et al. (2024) |
| `gender` | Matching (soft) | Nominal | Woman, Man, Non-binary or self-describe | Barnett et al. (2012); ONS (2023b) |
| `imd_quintile` | Drives isolation score | Ordinal | 1 (most deprived) to 5 | Uniform |
| `communication_language` | Hard rule | Nominal | English, Polish, Romanian, Panjabi, Urdu, Other | ONS (2022a) |
| `lives_alone` | Drives isolation score | True/False | | ONS (2022b, 2023a) |
| `primary_condition_category` | Hard rule | Nominal | Section 4 | Payne et al. (2020) |
| `primary_condition_subtype` | Matching | Nominal | Section 4 | Payne et al. (2020) |
| `condition_count` | Multimorbidity | Integer | 1 or more | Barnett et al. (2012) |
| `comorbidities` | Other conditions | Text, separated by `;` | Section 4 | Barnett et al. (2012) |
| `condition_duration_band` | Matching | Ordinal | <1, 1-2, 3-5, 6-10, 11-20, 20+ years | Limited by age band |
| `primary_support_goal` | Matching | Nominal | emotional_support, self_management_info, social_connection, accountability, shared_activity | Assumption |
| `support_orientation` | Matching (should be mixed) | Ordinal | Seeking, Balanced, Offering | Assumption |
| `psychosocial_isolation_score` | Matching (should be mixed) | Number, 20 to 80 | | Russell (1996); NHS England (2026); Holt-Lunstad et al. (2015) |
| `engagement_level` | Matching | Ordinal | Low, Medium, High | Assumption |

The exact weights and formulas are in `schema.py` and `data_generation.py`.

## 6. Consistency checks

Every generated dataset is checked against seven rules. Each count must be zero; any other value means a bug in the generator.

1. Every age band is one of the five bands.
2. The duration band fits within the adult years of the age band.
3. The condition sub-type belongs to its category.
4. No condition appears in an age band younger than its minimum onset age.
5. Comorbidities are distinct, do not repeat the primary condition, and match the condition count.
6. Every isolation score is between 20 and 80.
7. No profile is missing a field the hard rules need (age band, condition category, language).

## 7. Validation

`generate_dataset.py` writes a validation report for every dataset with:

- the seven consistency checks
- a chi-square goodness-of-fit test, using scipy, comparing the generated and target shares of language, gender and age band, with a p-value
- association checks: multimorbidity rises with age, isolation falls as deprivation falls, isolation is higher for people living alone, and the most common conditions follow the order in Payne et al. (2020)

Results:
- every dataset had zero consistency violations
- in the 50,000-profile dataset, the language test gave p = 0.023. To check whether this was a fault, 30 datasets of 50,000 profiles were generated: 4 of 90 tests (4.4%) had p < 0.05, in line with the 5% expected by chance, and no category was more than 0.6 percentage points from its target. The single result was chance, not a fault.
- in the 20 evaluation datasets of 3,000 profiles, 1 of 60 tests had p < 0.05

## 8. Code

- `schema.py`: the attributes, condition list and every calibration constant, each with its source. No generation logic.
- `data_generation.py`: generates one profile at a time and runs the consistency checks.
- `generate_dataset.py`: command line. Writes the dataset, the validation report and the figures.
- `visualize.py`: the eight figures.

The generator uses one seeded random number generator (`numpy.random.default_rng(seed)`). The same size and seed always give an identical file; this was checked by generating the 50,000-profile dataset twice and comparing the files.

## 9. Limitations

- All profiles are synthetic, so nothing about real peer-support outcomes follows from this data.
- Support goal, support orientation and engagement level are assumptions. This is why the weight sensitivity analysis is part of the evaluation.
- Condition weights are whole-population prevalences, not prevalences within an LTC population.
- Barnett et al. (2012) is a 2007 Scottish dataset of all ages and 40 conditions, used here for an adult, England-based, 11-condition dataset. It may slightly overstate multimorbidity.
- No published table gives the age profile of an LTC population for these bands, so the age weights are an informed estimate.
- Living-alone rates by age band are interpolated between two Census 2021 figures.
- The calibration is specific to England.

## 10. References

Barnett, K., Mercer, S. W., Norbury, M., Watt, G., Wyke, S., & Guthrie, B. (2012). Epidemiology of multimorbidity and implications for health care, research, and medical education: A cross-sectional study. *The Lancet, 380*(9836), 37–43. https://doi.org/10.1016/S0140-6736(12)60240-2

Holt-Lunstad, J., Smith, T. B., Baker, M., Harris, T., & Stephenson, D. (2015). Loneliness and social isolation as risk factors for mortality: A meta-analytic review. *Perspectives on Psychological Science, 10*(2), 227–237. https://doi.org/10.1177/1745691614568352

National Academies of Sciences, Engineering, and Medicine. (2020). *Social isolation and loneliness in older adults: Opportunities for the health care system.* The National Academies Press. https://doi.org/10.17226/25663

NHS England. (2026). *Health Survey for England, 2024: Loneliness and wellbeing.* NHS England Digital. https://digital.nhs.uk/data-and-information/publications/statistical/health-survey-for-england/2024

Office for National Statistics. (2022a). *Language, England and Wales: Census 2021.* https://www.ons.gov.uk/peoplepopulationandcommunity/culturalidentity/language/bulletins/languageenglandandwales/census2021

Office for National Statistics. (2022b). *Household and resident characteristics, England and Wales: Census 2021.* https://www.ons.gov.uk/peoplepopulationandcommunity/householdcharacteristics/homeinternetandsocialmediausage/bulletins/householdandresidentcharacteristicsenglandandwales/census2021

Office for National Statistics. (2023a). *People's living arrangements in England and Wales: Census 2021.* https://www.ons.gov.uk/peoplepopulationandcommunity/householdcharacteristics/homeinternetandsocialmediausage/articles/livingarrangementsofpeopleinenglandandwales/census2021

Office for National Statistics. (2023b). *Gender identity, England and Wales: Census 2021.* https://www.ons.gov.uk/peoplepopulationandcommunity/culturalidentity/genderidentity/bulletins/genderidentityenglandandwales/census2021

Payne, R. A., Mendonca, S. C., Elliott, M. N., Saunders, C. L., Edwards, D. A., Marshall, M., & Roland, M. (2020). Development and validation of the Cambridge Multimorbidity Score. *Canadian Medical Association Journal, 192*(5), E107–E114. https://doi.org/10.1503/cmaj.190757

Russell, D. W. (1996). UCLA Loneliness Scale (Version 3): Reliability, validity, and factor structure. *Journal of Personality Assessment, 66*(1), 20–40. https://doi.org/10.1207/s15327752jpa6601_2

Schubert, E., & Rousseeuw, P. J. (2021). Fast and eager k-medoids clustering: O(k) runtime improvement of the PAM, CLARA, and CLARANS algorithms. *Information Systems, 101*, 101804. https://doi.org/10.1016/j.is.2021.101804

Valabhji, J., Barron, E., Pratt, A., Hafezparast, N., Dunbar-Rees, R., Bragan Turner, E., Roberts, K., Mathews, J., Deegan, R., Cornelius, V., Pickles, J., Wainman, G., Bakhai, C., Johnston, D. G., Gregg, E. W., & Khunti, K. (2024). Prevalence of multiple long-term conditions (multimorbidity) in England: A whole population study of over 60 million people. *Journal of the Royal Society of Medicine, 117*(3). https://doi.org/10.1177/01410768231206033
