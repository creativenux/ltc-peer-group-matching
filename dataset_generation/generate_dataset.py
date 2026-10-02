"""
generate_dataset.py

Command line for the generator. Writes the dataset, a validation report
(consistency checks, chi-square tests against the calibration targets and
association checks) and eight figures.

Usage (from the project folder):
  python dataset_generation/generate_dataset.py                       # n=5000, seed=42
  python dataset_generation/generate_dataset.py --n 3000 --seed 42
  python dataset_generation/generate_dataset.py --n 3000 --replicates 20
  python dataset_generation/generate_dataset.py --format both        # CSV and JSON

Outputs (to --outdir, default output/n<n>):
  profiles_seed<seed>.csv                the dataset
  profiles_seed<seed>.json               with --format json or both
  validation_report_seed<seed>.md        the validation report
  profiles_seed<seed>_<figure>.png       eight figures
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.stats import chisquare

from schema import CONFIG
from data_generation import generate_dataset, audit_consistency
from visualize import generate_visualizations

# Datasets go to output/n<n>, where the matching code, the API and the web
# interface read them.
OUTPUT_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


def default_outdir(n: int) -> str:
    return os.path.join(OUTPUT_ROOT, f"n{n}")


# =============================================================================
# VALIDATION REPORT
# =============================================================================

def _chi_square_test(observed: list, expected: list) -> tuple:
    """Chi-square goodness-of-fit test (scipy). Returns (statistic, p_value)."""
    obs = np.array(observed, dtype=float)
    exp = np.array(expected, dtype=float)
    exp = exp * (obs.sum() / exp.sum())  # rescale expected to match observed total
    exp = np.where(exp == 0, 1e-9, exp)  # guard against division by zero
    statistic, p_value = chisquare(f_obs=obs, f_exp=exp)
    return float(statistic), float(p_value)


def _to_markdown(df: pd.DataFrame) -> str:
    """Render a DataFrame as a markdown table; fall back if tabulate is absent."""
    try:
        return df.to_markdown(index=False)
    except ImportError:
        return df.to_string(index=False)


def _categorical_report(df: pd.DataFrame, column: str, targets: dict, n: int):
    gen = df[column].value_counts(normalize=True)
    rows, obs_counts, exp_counts = [], [], []
    for cat, target in targets.items():
        g = float(gen.get(cat, 0.0))
        rows.append((cat, round(target, 4), round(g, 4), round(g - target, 4)))
        obs_counts.append(float((df[column] == cat).sum()))
        exp_counts.append(target * n)
    table = pd.DataFrame(rows, columns=[column, "target", "generated", "difference"])
    chi_sq, p_value = _chi_square_test(obs_counts, exp_counts)
    return table, chi_sq, p_value


def distributional_report(df: pd.DataFrame) -> str:
    """Compare generated distributions against their calibration targets."""
    n = len(df)
    out = ["## Distributional fidelity\n"]

    checks = {
        "communication_language": (CONFIG["language"], "Census 2021 main language, England (ONS, 2022)"),
        "gender": (CONFIG["gender"], "Women over-represented per Barnett et al. (2012)"),
        "age_band": (CONFIG["age_band_weights"], "LTC-shifted weights (Barnett et al., 2012; Valabhji et al., 2024)"),
    }
    for col, (targets, note) in checks.items():
        table, chi_sq, p_value = _categorical_report(df, col, targets, n)
        out.append(f"**{col}** — {note}\n")
        out.append(_to_markdown(table))
        interpretation = (
            "generated distribution is not significantly different from target (p >= 0.05)"
            if p_value >= 0.05 else
            "generated distribution differs significantly from target (p < 0.05); "
            "check sample size and target weights"
        )
        out.append(f"\nchi-square goodness-of-fit: statistic = {chi_sq:.2f}, p = {p_value:.4f} ({interpretation})\n")
    return "\n".join(out)


def association_report(df: pd.DataFrame) -> str:
    """Confirm the intended relationships are present, not just the marginals."""
    out = ["## Calibration-target reflection (associations)\n"]

    df = df.copy()
    df["is_multimorbid"] = df["condition_count"] >= 2
    by_age = df.groupby("age_band", observed=True)["is_multimorbid"].mean().reindex(
        list(CONFIG["age_band_weights"].keys())
    )
    out.append("**Multimorbidity rate by age band** (grounded in Barnett et al., 2012; expected to increase with age)\n")
    out.append(_to_markdown(by_age.round(3).to_frame("multimorbid_rate").reset_index()))
    out.append("")

    by_imd = df.groupby("imd_quintile")["psychosocial_isolation_score"].mean()
    out.append("**Mean isolation score by IMD quintile** (1 = most deprived; expected to fall as quintile rises)\n")
    out.append(_to_markdown(by_imd.round(2).to_frame("mean_isolation").reset_index()))
    out.append("")

    alone = df.groupby("lives_alone")["psychosocial_isolation_score"].mean()
    out.append("**Mean isolation score by living situation** (expected higher when living alone)\n")
    out.append(_to_markdown(alone.round(2).to_frame("mean_isolation").reset_index()))
    out.append("")

    thr = CONFIG["isolation_high_threshold"]
    high_share = float((df["psychosocial_isolation_score"] >= thr).mean())
    out.append(f"Share in the high-isolation band (score >= {thr:.0f}) = {high_share:.3f}.\n")

    all_conditions = []
    for _, row in df.iterrows():
        all_conditions.append(row["primary_condition_subtype"])
        all_conditions.extend([c for c in str(row["comorbidities"]).split(";") if c])
    top = pd.Series(all_conditions).value_counts(normalize=True).head(5)
    out.append("**Five most common conditions** (anxiety or depression and painful condition expected near the top; Payne et al., 2020)\n")
    out.append(_to_markdown(top.round(3).to_frame("share_of_all_condition_mentions").reset_index()))
    out.append("")
    return "\n".join(out)


def write_validation_report(df: pd.DataFrame, seed: int, path: str) -> None:
    n = len(df)
    audit = audit_consistency(df)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Validation report",
        f"Generated {ts}. Seed = {seed}. Profiles = {n}.\n",
        "## Logical consistency\n",
        "Every count below should be zero. A non-zero count means a generation bug.\n",
        _to_markdown(pd.Series(audit).to_frame("violations").reset_index()),
        "",
        distributional_report(df),
        association_report(df),
        "## Notes",
        "- Re-run with several seeds (or use --replicates) before trusting any single result.",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# =============================================================================
# OUTPUT AND CLI
# =============================================================================

def save_dataset(df: pd.DataFrame, outdir: str, seed: int, fmt: str) -> list:
    os.makedirs(outdir, exist_ok=True)
    written = []
    if fmt in ("csv", "both"):
        p = os.path.join(outdir, f"profiles_seed{seed}.csv")
        df.to_csv(p, index=False)
        written.append(p)
    if fmt in ("json", "both"):
        p = os.path.join(outdir, f"profiles_seed{seed}.json")
        df.to_json(p, orient="records", indent=2)
        written.append(p)
    return written


def parse_args():
    ap = argparse.ArgumentParser(
        description="Generate a synthetic UK LTC dataset for peer-group matching."
    )
    ap.add_argument("--n", type=int, default=5000,
                    help="profiles per dataset")
    ap.add_argument("--seed", type=int, default=42, help="random seed (reproducibility)")
    ap.add_argument("--replicates", type=int, default=1,
                    help="number of datasets, with seeds seed, seed+1, ...")
    ap.add_argument("--outdir", type=str, default=None,
                    help="output directory (default: output/n<n>)")
    ap.add_argument("--format", choices=["csv", "json", "both"], default="csv",
                    help="output format")
    return ap.parse_args()


def main():
    args = parse_args()
    args.outdir = args.outdir or default_outdir(args.n)
    print("Synthetic LTC data generator")
    print(f"  n={args.n}  base_seed={args.seed}  replicates={args.replicates}  outdir={args.outdir}")

    for r in range(args.replicates):
        seed = args.seed + r
        df = generate_dataset(args.n, seed)
        files = save_dataset(df, args.outdir, seed, args.format)
        report_path = os.path.join(args.outdir, f"validation_report_seed{seed}.md")
        write_validation_report(df, seed, report_path)

        audit = audit_consistency(df)
        status = "OK" if audit["TOTAL"] == 0 else f"{audit['TOTAL']} VIOLATIONS"
        print(f"  seed {seed}: wrote {', '.join(files)} + validation report  [consistency: {status}]")

        plot_paths = generate_visualizations(df, args.outdir, seed)
        print(f"  seed {seed}: wrote {len(plot_paths)} figures")

    print("Done.")


if __name__ == "__main__":
    main()
