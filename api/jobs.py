"""
jobs.py

Runs the evaluation in the background, since it takes several minutes. It
generates any missing replicate datasets, then runs run_evaluation.py. Only
one job runs at a time.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time

import paths


class EvaluationJob:
    def __init__(self):
        self._lock = threading.Lock()
        self.status = "idle"          # idle | running | done | failed
        self.params: dict = {}
        self.log: list = []
        self.started = self.finished = None

    def snapshot(self) -> dict:
        with self._lock:
            return {"status": self.status, "params": self.params, "log": self.log[-200:],
                    "started": self.started, "finished": self.finished}

    def start(self, n: int, seed: int, replicates: int) -> bool:
        with self._lock:
            if self.status == "running":
                return False
            self.status, self.params, self.log = "running", {
                "n": n, "seed": seed, "replicates": replicates}, []
            self.started, self.finished = time.time(), None
        threading.Thread(target=self._run, args=(n, seed, replicates), daemon=True).start()
        return True

    def _append(self, line: str):
        with self._lock:
            self.log.append(line.rstrip())

    def _stream(self, command: list) -> int:
        self._append("$ " + " ".join(str(c) for c in command[1:]))
        process = subprocess.Popen([str(c) for c in command], stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, cwd=paths.ROOT)
        for line in process.stdout:
            self._append(line)
        return process.wait()

    def _run(self, n: int, seed: int, replicates: int):
        data_dir = paths.dataset_dir(n)
        missing = [s for s in range(seed, seed + replicates)
                   if not (data_dir / f"profiles_seed{s}.csv").exists()]
        code = 0
        if missing:
            code = self._stream([sys.executable, paths.GENERATOR_DIR / "generate_dataset.py",
                                 "--n", n, "--seed", seed, "--replicates", replicates,
                                 "--outdir", data_dir])
        if code == 0:
            code = self._stream([sys.executable, paths.ROOT / "run_evaluation.py",
                                 "--n", n, "--seed", seed, "--replicates", replicates,
                                 "--datadir", data_dir,
                                 "--outdir", paths.OUTPUT_DIR / "evaluation"])
        with self._lock:
            self.status = "done" if code == 0 else "failed"
            self.finished = time.time()


JOB = EvaluationJob()
