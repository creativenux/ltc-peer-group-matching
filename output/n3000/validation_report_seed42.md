# Validation report
Generated 2026-09-25 17:07 UTC. Seed = 42. Profiles = 3000.

## Logical consistency

Every count below should be zero. A non-zero count means a generation bug.

| index                          |   violations |
|:-------------------------------|-------------:|
| invalid_age_band               |            0 |
| duration_exceeds_band          |            0 |
| subtype_parent_mismatch        |            0 |
| condition_implausible_for_band |            0 |
| comorbidity_incoherent         |            0 |
| isolation_out_of_range         |            0 |
| missing_hard_rule_fields       |            0 |
| TOTAL                          |            0 |

## Distributional fidelity

**communication_language** — Census 2021 main language, England (ONS, 2022)

| communication_language   |   target |   generated |   difference |
|:-------------------------|---------:|------------:|-------------:|
| English                  |    0.908 |      0.9187 |       0.0107 |
| Polish                   |    0.011 |      0.0093 |      -0.0017 |
| Romanian                 |    0.009 |      0.0073 |      -0.0017 |
| Panjabi                  |    0.005 |      0.0057 |       0.0007 |
| Urdu                     |    0.005 |      0.003  |      -0.002  |
| Other                    |    0.062 |      0.056  |      -0.006  |

chi-square goodness-of-fit: statistic = 6.47, p = 0.2633 (generated distribution is not significantly different from target (p >= 0.05))

**gender** — Women over-represented per Barnett et al. (2012)

| gender                      |   target |   generated |   difference |
|:----------------------------|---------:|------------:|-------------:|
| Woman                       |    0.52  |      0.511  |      -0.009  |
| Man                         |    0.475 |      0.4823 |       0.0073 |
| Non-binary or self-describe |    0.005 |      0.0067 |       0.0017 |

chi-square goodness-of-fit: statistic = 2.47, p = 0.2903 (generated distribution is not significantly different from target (p >= 0.05))

**age_band** — LTC-shifted weights (Barnett et al., 2012; Valabhji et al., 2024)

| age_band   |   target |   generated |   difference |
|:-----------|---------:|------------:|-------------:|
| 18-29      |     0.05 |       0.053 |        0.003 |
| 30-44      |     0.12 |       0.119 |       -0.001 |
| 45-59      |     0.25 |       0.244 |       -0.006 |
| 60-74      |     0.33 |       0.337 |        0.007 |
| 75+        |     0.25 |       0.247 |       -0.003 |

chi-square goodness-of-fit: statistic = 1.55, p = 0.8177 (generated distribution is not significantly different from target (p >= 0.05))

## Calibration-target reflection (associations)

**Multimorbidity rate by age band** (grounded in Barnett et al., 2012; expected to increase with age)

| age_band   |   multimorbid_rate |
|:-----------|-------------------:|
| 18-29      |              0.34  |
| 30-44      |              0.395 |
| 45-59      |              0.523 |
| 60-74      |              0.617 |
| 75+        |              0.679 |

**Mean isolation score by IMD quintile** (1 = most deprived; expected to fall as quintile rises)

|   imd_quintile |   mean_isolation |
|---------------:|-----------------:|
|              1 |            52    |
|              2 |            49.19 |
|              3 |            46.2  |
|              4 |            44.52 |
|              5 |            41.77 |

**Mean isolation score by living situation** (expected higher when living alone)

| lives_alone   |   mean_isolation |
|:--------------|-----------------:|
| False         |            45.06 |
| True          |            51.49 |

Share in the high-isolation band (score >= 50) = 0.388.

**Five most common conditions** (anxiety or depression and painful condition expected near the top; Payne et al., 2020)

| index                  |   share_of_all_condition_mentions |
|:-----------------------|----------------------------------:|
| Anxiety or depression  |                             0.251 |
| Painful condition      |                             0.175 |
| Diabetes mellitus      |                             0.125 |
| Coronary heart disease |                             0.087 |
| Chronic kidney disease |                             0.087 |

## Notes
- Re-run with several seeds (or use --replicates) before trusting any single result.