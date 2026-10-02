"""
visualize.py

Eight figures for a generated dataset, each saved as a PNG with a short
source caption. They show whether the data matches its calibration targets
and whether the intended relationships are present: multimorbidity rising
with age, and isolation rising with deprivation and with living alone.
"""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")  # no display available in this environment
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

from schema import CONFIG

sns.set_theme(style="white", context="talk", font_scale=0.85)
PALETTE = sns.color_palette("mako", 8)
ACCENT = PALETTE[3]
MUTED = PALETTE[1]
FIGSIZE = (9, 6)
DPI = 220


def _age_band_order() -> list:
    return list(CONFIG["age_band_weights"].keys())


def _finish(fig, ax, caption: str) -> None:
    """Shared styling: strip top/right spines and add a source caption in a
    reserved bottom margin, below the x-axis label rather than overlapping it."""
    sns.despine(ax=ax)
    fig.tight_layout(rect=[0, 0.07, 1, 1])  # reserve bottom margin for the caption
    fig.text(0.02, 0.015, caption, fontsize=10, color="dimgray", style="italic",
              ha="left", va="bottom", transform=fig.transFigure)


def _save(fig, outdir: str, seed: int, name: str) -> str:
    path = os.path.join(outdir, f"profiles_seed{seed}_{name}.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path


# =============================================================================
# INDIVIDUAL FIGURES
# =============================================================================

def plot_age_band(df: pd.DataFrame, outdir: str, seed: int) -> str:
    order = _age_band_order()
    counts = df["age_band"].value_counts(normalize=True).reindex(order)
    targets = pd.Series(CONFIG["age_band_weights"]).reindex(order)

    fig, ax = plt.subplots(figsize=FIGSIZE)
    x = range(len(order))
    width = 0.36
    ax.bar([i - width / 2 for i in x], counts.values, width, label="Generated",
           color=ACCENT, edgecolor="white")
    ax.bar([i + width / 2 for i in x], targets.values, width, label="Target",
           color="lightgray", edgecolor="dimgray")
    ax.set_xticks(list(x))
    ax.set_xticklabels(order)
    ax.set_ylabel("Share of profiles")
    ax.set_xlabel("Age band")
    ax.set_title("Age band distribution: generated vs target", fontweight="bold", pad=14)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.legend(frameon=False)
    _finish(fig, ax, "Target weights informed by Barnett et al. (2012) and Valabhji et al. (2024).")
    return _save(fig, outdir, seed, "age_band")


def plot_condition_mix(df: pd.DataFrame, outdir: str, seed: int) -> str:
    all_conditions = []
    for _, row in df.iterrows():
        all_conditions.append(row["primary_condition_subtype"])
        all_conditions.extend([c for c in str(row["comorbidities"]).split(";") if c])
    counts = pd.Series(all_conditions).value_counts(normalize=True).sort_values()

    fig, ax = plt.subplots(figsize=(9, 7))
    bars = ax.barh(counts.index, counts.values, color=PALETTE[4])
    ax.bar_label(bars, labels=[f"{v:.1%}" for v in counts.values], padding=4, fontsize=10)
    ax.set_xlabel("Share of all condition mentions")
    ax.set_title("Condition mix across the dataset", fontweight="bold", pad=14)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_xlim(0, counts.max() * 1.18)
    _finish(fig, ax, "Condition list and prevalence weights: Payne et al. (2020), Table 2.")
    return _save(fig, outdir, seed, "condition_mix")


def plot_multimorbidity_by_age(df: pd.DataFrame, outdir: str, seed: int) -> str:
    order = _age_band_order()
    df = df.copy()
    df["is_multimorbid"] = df["condition_count"] >= 2
    rate = df.groupby("age_band", observed=True)["is_multimorbid"].mean().reindex(order)

    fig, ax = plt.subplots(figsize=FIGSIZE)
    bars = ax.bar(order, rate.values, color=MUTED)
    ax.bar_label(bars, labels=[f"{v:.0%}" for v in rate.values], padding=4)
    ax.set_ylabel("Share with 2 or more conditions")
    ax.set_xlabel("Age band")
    ax.set_title("Multimorbidity rises with age", fontweight="bold", pad=14)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_ylim(0, max(rate.values) * 1.2)
    _finish(fig, ax, "Age gradient grounded in Barnett et al. (2012), Table 1.")
    return _save(fig, outdir, seed, "multimorbidity_by_age")


def plot_isolation_distribution(df: pd.DataFrame, outdir: str, seed: int) -> str:
    threshold = CONFIG["isolation_high_threshold"]
    fig, ax = plt.subplots(figsize=FIGSIZE)
    sns.histplot(df["psychosocial_isolation_score"], bins=24, ax=ax, color=ACCENT, edgecolor="white")
    ax.axvline(threshold, color="firebrick", linestyle="--", linewidth=2)
    ax.text(threshold + 1.5, ax.get_ylim()[1] * 0.92, f"high-isolation\nthreshold ({threshold:.0f})",
            color="firebrick", fontsize=11, va="top")
    ax.set_xlabel("Psychosocial isolation score (UCLA-derived, 20 to 80)")
    ax.set_ylabel("Number of profiles")
    ax.set_title("Distribution of the psychosocial isolation score", fontweight="bold", pad=14)
    _finish(fig, ax, "Construct based on Russell (1996); threshold consistent with published loneliness-trial categorisation.")
    return _save(fig, outdir, seed, "isolation_distribution")


def plot_isolation_by_imd(df: pd.DataFrame, outdir: str, seed: int) -> str:
    means = df.groupby("imd_quintile")["psychosocial_isolation_score"].mean().sort_index()
    fig, ax = plt.subplots(figsize=FIGSIZE)
    bars = ax.bar(means.index.astype(str), means.values, color=PALETTE[5])
    ax.bar_label(bars, labels=[f"{v:.1f}" for v in means.values], padding=4)
    ax.set_xlabel("IMD quintile (1 = most deprived, 5 = least deprived)")
    ax.set_ylabel("Mean isolation score")
    ax.set_title("Isolation falls as deprivation eases", fontweight="bold", pad=14)
    ax.set_ylim(0, max(means.values) * 1.2)
    _finish(fig, ax, "Deprivation gradient consistent with NHS England (2026), Health Survey for England.")
    return _save(fig, outdir, seed, "isolation_by_imd")


def plot_isolation_by_living_alone(df: pd.DataFrame, outdir: str, seed: int) -> str:
    means = df.groupby("lives_alone")["psychosocial_isolation_score"].mean()
    labels = ["Lives with others", "Lives alone"]
    values = [means.get(False, 0.0), means.get(True, 0.0)]

    fig, ax = plt.subplots(figsize=FIGSIZE)
    bars = ax.bar(labels, values, color=[PALETTE[2], PALETTE[6]])
    ax.bar_label(bars, labels=[f"{v:.1f}" for v in values], padding=4)
    ax.set_ylabel("Mean isolation score")
    ax.set_title("Isolation score by living situation", fontweight="bold", pad=14)
    ax.set_ylim(0, max(values) * 1.2)
    _finish(fig, ax, "Consistent with the mortality risk of living alone reported by Holt-Lunstad et al. (2015).")
    return _save(fig, outdir, seed, "isolation_by_living_alone")


def plot_support_goal(df: pd.DataFrame, outdir: str, seed: int) -> str:
    counts = df["primary_support_goal"].value_counts(normalize=True).sort_values()
    fig, ax = plt.subplots(figsize=(9, 6))
    bars = ax.barh(counts.index, counts.values, color=PALETTE[3])
    ax.bar_label(bars, labels=[f"{v:.1%}" for v in counts.values], padding=4, fontsize=10)
    ax.set_xlabel("Share of profiles")
    ax.set_title("Primary support goal", fontweight="bold", pad=14)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_xlim(0, counts.max() * 1.2)
    _finish(fig, ax, "Category set and split agreed with supervisor; no population statistic exists for this attribute.")
    return _save(fig, outdir, seed, "support_goal")


def plot_condition_count(df: pd.DataFrame, outdir: str, seed: int) -> str:
    counts = df["condition_count"].value_counts(normalize=True).sort_index()
    fig, ax = plt.subplots(figsize=FIGSIZE)
    bars = ax.bar(counts.index.astype(str), counts.values, color=MUTED)
    ax.bar_label(bars, labels=[f"{v:.1%}" for v in counts.values], padding=4)
    ax.set_xlabel("Number of conditions")
    ax.set_ylabel("Share of profiles")
    ax.set_title("Condition count distribution", fontweight="bold", pad=14)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_ylim(0, max(counts.values) * 1.2)
    _finish(fig, ax, "Count distribution given multimorbid derived from Barnett et al. (2012), Table 1.")
    return _save(fig, outdir, seed, "condition_count")


# =============================================================================
# ENTRY POINT
# =============================================================================

def generate_visualizations(df: pd.DataFrame, outdir: str, seed: int) -> list:
    """Build all figures and save each as a PNG.

    Returns the list of saved file paths.
    """
    os.makedirs(outdir, exist_ok=True)
    plotters = [
        plot_age_band,
        plot_condition_mix,
        plot_multimorbidity_by_age,
        plot_isolation_distribution,
        plot_isolation_by_imd,
        plot_isolation_by_living_alone,
        plot_support_goal,
        plot_condition_count,
    ]
    return [fn(df, outdir, seed) for fn in plotters]