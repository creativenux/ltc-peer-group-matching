"""End to end: generate replicates, evaluate, write report and JSON."""

import json
import subprocess
import sys

import paths


def test_run_evaluation_writes_report_and_json(tmp_path):
    data_dir = tmp_path / "n250"
    gen = subprocess.run([sys.executable, str(paths.GENERATOR_DIR / "generate_dataset.py"),
                          "--n", "250", "--seed", "10", "--replicates", "3",
                          "--outdir", str(data_dir)], capture_output=True, text=True)
    assert gen.returncode == 0, gen.stderr

    ev = subprocess.run([sys.executable, str(paths.ROOT / "run_evaluation.py"),
                         "--n", "250", "--seed", "10", "--replicates", "3", "--workers", "1",
                         "--datadir", str(data_dir), "--outdir", str(tmp_path / "evaluation")],
                        capture_output=True, text=True)
    assert ev.returncode == 0, ev.stderr

    out = json.loads((tmp_path / "evaluation" / "evaluation_n250.json").read_text())
    assert out["seeds"] == [10, 11, 12]
    assert len(out["replicates"]) == 3
    assert set(out["replicates"][0]["metrics"]) == {
        "weighted_gower", "unweighted_gower", "single_age_band",
        "single_primary_support_goal", "random"}
    assert "cohesion_index" in out["tests"]
    assert len(out["sensitivity"]["ranking"]) == 8

    report = (tmp_path / "evaluation" / "evaluation_report_n250.md").read_text()
    assert report.count("### For the dissertation") == 3
    assert "## Limitations" in report


def test_missing_replicates_are_named_with_the_command_to_generate_them(tmp_path):
    ev = subprocess.run([sys.executable, str(paths.ROOT / "run_evaluation.py"),
                         "--n", "250", "--seed", "10", "--replicates", "2",
                         "--datadir", str(tmp_path)], capture_output=True, text=True)
    assert ev.returncode != 0
    assert "generate_dataset.py --n 250 --seed 10 --replicates 2" in ev.stderr


def test_report_tables_are_exported_as_csv(tmp_path):
    import csv
    from evaluation.report import write_csv_tables
    results = json.loads((paths.OUTPUT_DIR / "evaluation" / "evaluation_n3000.json").read_text())
    files = write_csv_tables(results, tmp_path)
    names = {f.name for f in files}
    assert names == {"evaluation_n3000_metrics.csv", "evaluation_n3000_attribute_dissimilarity.csv",
                     "evaluation_n3000_statistical_tests.csv", "evaluation_n3000_sensitivity.csv",
                     "evaluation_n3000_replicates.csv"}
    rows = list(csv.DictReader(open(tmp_path / "evaluation_n3000_metrics.csv", encoding="utf-8-sig")))
    assert [r["Method"] for r in rows][0] == "Weighted Gower (full method)"
    assert float(rows[0]["Silhouette (weighted Gower matrix) mean"]) == round(
        results["summary"]["silhouette_weighted"]["weighted_gower"]["mean"], 4)
    reps = list(csv.DictReader(open(tmp_path / "evaluation_n3000_replicates.csv", encoding="utf-8-sig")))
    assert len(reps) == len(results["seeds"]) * len(results["methods"])
