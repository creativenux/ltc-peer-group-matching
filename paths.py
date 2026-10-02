"""
paths.py

Folder locations shared by every script, so results always go to the same
place whichever folder a script is run from.

  dataset_generation/   the synthetic data generator
  output/n<n>/          datasets, validation reports and figures for size n
  output/matching/      matching results
  output/evaluation/    evaluation results and report

Importing this module also adds dataset_generation/ to the import path,
because the generator modules import each other by name (from schema import ...).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GENERATOR_DIR = ROOT / "dataset_generation"
OUTPUT_DIR = ROOT / "output"
MATCHING_DIR = OUTPUT_DIR / "matching"

if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))


def dataset_dir(n: int) -> Path:
    """Folder for datasets of size n (kept apart so sizes never overwrite each other)."""
    return OUTPUT_DIR / f"n{n}"


def dataset_csv(n: int, seed: int) -> Path:
    return dataset_dir(n) / f"profiles_seed{seed}.csv"
