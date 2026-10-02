"""Command-line flow: generate a dataset, then match it."""

import json
import subprocess
import sys

import paths

ROOT = paths.ROOT


def test_generate_then_match(tmp_path):
    data_dir = tmp_path / "n300"
    gen = subprocess.run([sys.executable, str(paths.GENERATOR_DIR / "generate_dataset.py"),
                          "--n", "300", "--seed", "3", "--outdir", str(data_dir)],
                         cwd=tmp_path, capture_output=True, text=True)
    assert gen.returncode == 0, gen.stderr

    match = subprocess.run([sys.executable, str(ROOT / "run_matching.py"),
                            "--input", str(data_dir / "profiles_seed3.csv"), "--seed", "3",
                            "--outdir", str(tmp_path / "matching")],
                           cwd=tmp_path, capture_output=True, text=True)
    assert match.returncode == 0, match.stderr
    out = json.loads((tmp_path / "matching" / "matching_n300_seed3.json").read_text())
    assert set(out["methods"]) == {"weighted_gower", "unweighted_gower", "single_age_band",
                                   "single_primary_support_goal", "random"}
    group = out["methods"]["weighted_gower"]["groups"][0]
    assert {"group_id", "members", "score", "explanation"} <= set(group)
    unmatched = out["methods"]["weighted_gower"]["unmatched"]
    assert all({"reason", "plain_language"} <= set(u) for u in unmatched)
    assert "weighted_gower" in match.stdout
