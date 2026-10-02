# Peer Group Matching for People with Long-Term Conditions

A transparent, rules-based system that forms peer support groups of six to eight people living with long-term health conditions. It tests whether matching on several weighted attributes forms more cohesive groups than random assignment or matching on a single attribute.

Toheeb Olayemi, MSc Applied Artificial Intelligence, University of Chester.

All data is synthetic. No real people or patient records are used, and no machine-learned model makes any matching decision.

## How it works

1. **Synthetic data.** Profiles of UK adults with long-term conditions are generated from published UK figures, then checked for consistency and against their targets.
2. **Hard rules.** People are split into pools that share a condition category and a language. Groups are formed inside a pool and have six to eight members.
3. **Weighted Gower similarity.** Profiles are compared on condition sub-type, support goal, age band, time with the condition, gender and engagement level, each with its own weight.
4. **Group assembly.** Groups are built greedily, then improved by swapping members. The group score rewards shared attributes and a mix of support orientation and isolation level.
5. **Explanations.** Every group and every unmatched person gets a plain-language explanation.
6. **Evaluation.** The method is compared with random assignment, age-band matching, support-goal matching and an unweighted version, across 20 datasets, using silhouette, within-group distance, Friedman and Wilcoxon tests, and a weight sensitivity analysis.

## Result

Across 20 datasets of 3,000 profiles, the weighted method formed more cohesive groups than random assignment and both single-attribute methods in every dataset (Holm-adjusted p < 0.001, rank-biserial r = 1.00).

| Method | Silhouette (weighted Gower) | Within-group distance |
|---|---|---|
| Weighted Gower | 0.133 | 0.116 |
| Unweighted Gower | 0.056 | 0.141 |
| Support goal only | −0.232 | 0.246 |
| Age band only | −0.244 | 0.384 |
| Random | −0.294 | 0.435 |

The full results are produced by `run_evaluation.py` (see below).

## Project layout

```
├── dataset_generation/   synthetic data generator and its specification
├── matching/             hard rules, weighted Gower, group assembly, baselines, explanations
├── evaluation/           metrics, statistical tests, sensitivity analysis, report
├── api/                  FastAPI backend for the web interface
├── web/                  web interface (HTML, Tailwind CSS, JavaScript)
├── tests/                automated tests
├── output/               generated datasets and results (not tracked by git)
├── paths.py              folder locations used by every script
├── run_matching.py       match one dataset
├── run_evaluation.py     run the full evaluation
└── DECISIONS.md          design decisions
```

## Setup

Tested with Python 3.13.

```bash
pip install -r requirements.txt
```

## Usage

Run every command from the project folder.

```bash
# Generate a dataset (written to output/n3000/)
python dataset_generation/generate_dataset.py --n 3000 --seed 42

# Match it with every method (written to output/matching/)
python run_matching.py --n 3000 --seed 42

# Full evaluation: 20 datasets, all methods, statistical tests and sensitivity analysis
# (about 6 minutes; written to output/evaluation/)
python dataset_generation/generate_dataset.py --n 3000 --seed 42 --replicates 20
python run_evaluation.py --n 3000 --seed 42 --replicates 20

# Tests
python -m pytest
```

## Web interface

```bash
uvicorn api.app:app
```

Open http://127.0.0.1:8000. The interface lets you generate and validate a dataset, run matching, inspect the hard rules, explore groups on a map, look up any profile, and view or re-run the evaluation. API documentation is at http://127.0.0.1:8000/api/docs.

## Online version

`render.yaml` deploys the web interface to [Render](https://render.com) as a view-only. With `READ_ONLY=1`, generating data, running matching and running the evaluation are turned off, and the site shows the results committed in `output/` (the 3,000-profile dataset with seed 42, its matching results and the evaluation).

## Documentation

- [DECISIONS.md](DECISIONS.md): design decisions and the reason for each
- [dataset_generation/synthetic_data_generation_specification_v2.md](dataset_generation/synthetic_data_generation_specification_v2.md): how the synthetic data is generated and validated
