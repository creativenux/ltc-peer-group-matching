"""
run_matching.py

Runs the matching method and all baselines on one dataset and saves the
result as JSON: the groups, their explanations, every unmatched profile with
its reason, the hard-rule audit and the run times.

Usage:
  python dataset_generation/generate_dataset.py --n 3000 --seed 42
  python run_matching.py --n 3000 --seed 42
  python run_matching.py --input path/to/profiles.csv
  python run_matching.py --methods weighted_gower random

Reads output/n<n>/profiles_seed<seed>.csv unless --input is given.
Writes output/matching/matching_n<n>_seed<seed>.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import paths
from matching.explainability import explain_unmatched
from matching.pipeline import METHODS, load_profiles, run_all_methods


def run_to_dict(run) -> dict:
    """A JSON-serialisable view of a MatchingRun."""
    return {
        "seed": run.seed,
        "n_profiles": run.n_profiles,
        "hard_rules": {"rules": run.audit.rules, "pools": run.audit.pools},
        "methods": {
            name: {
                "seconds": round(outcome.seconds, 3),
                "n_groups": len(outcome.groups),
                "n_unmatched": len(outcome.unmatched),
                "groups": outcome.group_records(),
                "unmatched": [{"profile_id": pid, "reason": reason,
                               "plain_language": explain_unmatched(reason)}
                              for pid, reason in outcome.unmatched.items()],
                "pool_logs": [{"pool": list(r.pool_key), "stopping": r.stopping,
                               "passes": r.passes, "swaps": r.swaps, "log": r.log}
                              for r in outcome.pool_results],
            }
            for name, outcome in run.methods.items()
        },
    }


def parse_args():
    ap = argparse.ArgumentParser(description="Run the peer group matching engine and baselines.")
    ap.add_argument("--n", type=int, default=3000, help="dataset size to read from output/n<n>/")
    ap.add_argument("--seed", type=int, default=42, help="dataset seed; also seeds the matching")
    ap.add_argument("--input", type=str, default=None, help="read this profiles CSV instead")
    ap.add_argument("--methods", nargs="+", choices=list(METHODS), default=list(METHODS))
    ap.add_argument("--outdir", type=str, default=str(paths.MATCHING_DIR), help="output directory")
    return ap.parse_args()


def main():
    args = parse_args()
    source = Path(args.input) if args.input else paths.dataset_csv(args.n, args.seed)
    if not source.exists():
        sys.exit(f"Dataset not found: {source}\n"
                 f"Generate it first:  python dataset_generation/generate_dataset.py "
                 f"--n {args.n} --seed {args.seed}")
    df = load_profiles(source)
    print(f"Peer group matching: {source} (n={len(df)}, seed={args.seed})")

    run = run_all_methods(df, seed=args.seed, methods=args.methods)
    viable = sum(p["viable"] for p in run.audit.pools)
    print(f"  hard rules: {len(run.audit.pools)} pools, {viable} can form at least one group, "
          f"{len(run.audit.excluded)} profiles in pools too small to group")
    for name, outcome in run.methods.items():
        print(f"  {name:28s} {len(outcome.groups):5d} groups  "
              f"{len(outcome.unmatched):4d} unmatched  {outcome.seconds:6.1f}s")

    os.makedirs(args.outdir, exist_ok=True)
    path = Path(args.outdir) / f"matching_n{len(df)}_seed{args.seed}.json"
    path.write_text(json.dumps(run_to_dict(run), indent=1, default=float))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
