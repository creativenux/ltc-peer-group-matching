"""Where the generator and the matching runner read and write."""

import subprocess
import sys

import paths

ROOT = paths.ROOT


def test_dataset_location_is_under_output_by_size():
    assert paths.dataset_csv(3000, 42) == ROOT / "output" / "n3000" / "profiles_seed42.csv"


def test_generator_defaults_to_output_whatever_the_working_directory():
    sys.path.insert(0, str(paths.GENERATOR_DIR))
    from generate_dataset import default_outdir
    assert default_outdir(3000) == str(ROOT / "output" / "n3000")


def test_run_matching_explains_how_to_generate_a_missing_dataset(tmp_path):
    proc = subprocess.run([sys.executable, str(ROOT / "run_matching.py"), "--n", "123",
                           "--seed", "987654", "--outdir", str(tmp_path)],
                          cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "generate_dataset.py --n 123 --seed 987654" in proc.stderr
