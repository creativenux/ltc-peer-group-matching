"""
run_evaluation.py

Compares the weighted Gower method with every baseline across replicate
datasets: cohesion metrics, Friedman and Wilcoxon tests, and the weight
sensitivity analysis.

Usage:
  python dataset_generation/generate_dataset.py --n 3000 --seed 42 --replicates 20
  python run_evaluation.py --n 3000 --seed 42 --replicates 20

Reads output/n<n>/profiles_seed<seed>.csv for each replicate seed.
Writes to output/evaluation/:
  evaluation_n<n>.json            all results
  evaluation_report_n<n>.md       the report
  evaluation_n<n>_<table>.csv     each report table, plus per-replicate metrics
"""

from __future__ import annotations

import os

# One maths-library thread per process: the workers already use every core,
# and extra threads per worker made each replicate several times slower.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import paths
from evaluation.metrics import evaluate_run
from evaluation.report import METRICS, REFERENCE, build_report, write_csv_tables
from evaluation.sensitivity import run_sensitivity
from evaluation.statistical_tests import compare_methods
from matching.attributes import HOMOGENEITY_ATTRIBUTES
from matching.pipeline import METHODS, load_profiles, run_all_methods


def evaluate_replicate(args) -> dict:
    path, seed = args
    run = run_all_methods(load_profiles(path), seed=seed)
    return {"seed": seed, "metrics": evaluate_run(run),
            "seconds": {m: o.seconds for m, o in run.methods.items()}}


def _clean(value):
    """NaN becomes None so the JSON is standard and readable by the web app."""
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def summarise(replicates: list, methods: list) -> tuple:
    summary, tests = {}, {}
    for metric, (_, higher_is_better) in METRICS.items():
        table = {m: [r["metrics"][m][metric] for r in replicates] for m in methods}
        summary[metric] = {m: {"mean": float(np.nanmean(v)), "sd": float(np.nanstd(v, ddof=1))}
                           for m, v in table.items()}
        keep = [i for i in range(len(replicates))
                if not any(math.isnan(table[m][i]) for m in methods)]
        table = {m: [v[i] for i in keep] for m, v in table.items()}
        tests[metric] = compare_methods(table, REFERENCE, higher_is_better)
    within = {m: {a: float(np.mean([r["metrics"][m]["within_group_dissimilarity"][a]
                                    for r in replicates]))
                  for a in HOMOGENEITY_ATTRIBUTES} for m in methods}
    return summary, tests, within


def parse_args():
    ap = argparse.ArgumentParser(description="Evaluate the matching methods across replicates.")
    ap.add_argument("--n", type=int, default=3000, help="dataset size")
    ap.add_argument("--seed", type=int, default=42, help="first replicate seed")
    ap.add_argument("--replicates", type=int, default=20, help="number of replicate datasets")
    ap.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 2) // 2)),
                    help="parallel processes (default: half the cores, at most 4)")
    ap.add_argument("--datadir", type=str, default=None,
                    help="folder with the replicate CSVs (default: output/n<n>)")
    ap.add_argument("--outdir", type=str, default=str(paths.OUTPUT_DIR / "evaluation"))
    return ap.parse_args()


def main():
    args = parse_args()
    datadir = Path(args.datadir) if args.datadir else paths.dataset_dir(args.n)
    seeds = list(range(args.seed, args.seed + args.replicates))
    files = [datadir / f"profiles_seed{s}.csv" for s in seeds]
    missing = [f for f in files if not f.exists()]
    if missing:
        sys.exit(f"{len(missing)} of {len(files)} replicate datasets not found in {datadir}\n"
                 f"Generate them first:  python dataset_generation/generate_dataset.py "
                 f"--n {args.n} --seed {args.seed} --replicates {args.replicates}")

    start = time.perf_counter()
    print(f"Evaluating {len(seeds)} replicates of n={args.n} with {args.workers} worker(s)", flush=True)
    jobs = list(zip(files, seeds))
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            replicates = []
            for r in pool.map(evaluate_replicate, jobs):
                replicates.append(r)
                print(f"  replicate seed {r['seed']} done", flush=True)
    else:
        replicates = [evaluate_replicate(j) for j in jobs]

    methods = list(METHODS)
    summary, tests, within = summarise(replicates, methods)

    print(f"Sensitivity analysis on seed {seeds[0]}", flush=True)
    sensitivity = run_sensitivity(load_profiles(files[0]), seed=seeds[0], workers=args.workers)

    results = {
        "n": args.n, "seeds": seeds, "methods": methods,
        "replicates": replicates, "summary": summary, "tests": tests,
        "within_group_dissimilarity": within, "sensitivity": sensitivity,
        "runtime_seconds": time.perf_counter() - start,
    }

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    json_path = outdir / f"evaluation_n{args.n}.json"
    report_path = outdir / f"evaluation_report_n{args.n}.md"
    json_path.write_text(json.dumps(_clean(results), indent=1))
    report_path.write_text(build_report(results))
    csv_files = write_csv_tables(results, outdir)
    print(f"Wrote {json_path}\nWrote {report_path}")
    for f in csv_files:
        print(f"Wrote {f}")


if __name__ == "__main__":
    main()
