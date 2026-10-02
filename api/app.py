"""
app.py

Serves the web interface (web/) and a JSON API for the dataset generator,
the matching method and the evaluation. Reads and writes the output folder.

Run from the project folder:
  uvicorn api.app:app --reload
then open http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import paths
from api.group_map import classical_mds
from api.jobs import JOB
from data_generation import audit_consistency, generate_dataset
from generate_dataset import _categorical_report, save_dataset, write_validation_report
from matching.attributes import DEFAULT_WEIGHTS
from matching.explainability import explain_unmatched
from matching.hard_rules import partition_into_eligible_pools
from matching.pipeline import METHODS, load_profiles, run_all_methods
from matching.similarity import compute_gower_distance_matrix
from run_matching import run_to_dict
from schema import CONFIG
from visualize import generate_visualizations

WEB_DIR = paths.ROOT / "web"

app = FastAPI(title="Peer group matching", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

FIGURES = [
    ("age_band", "Age band distribution"),
    ("condition_mix", "Primary condition mix"),
    ("multimorbidity_by_age", "Multimorbidity by age band"),
    ("isolation_distribution", "Isolation score distribution"),
    ("isolation_by_imd", "Isolation by deprivation quintile"),
    ("isolation_by_living_alone", "Isolation by living situation"),
    ("support_goal", "Primary support goal"),
    ("condition_count", "Number of conditions"),
]

CHI_SQUARE_TARGETS = {
    "communication_language": (CONFIG["language"], "Census 2021 main language, England (ONS, 2022)"),
    "gender": (CONFIG["gender"], "Barnett et al. (2012)"),
    "age_band": (CONFIG["age_band_weights"], "Barnett et al. (2012); Valabhji et al. (2024)"),
}

FILTER_COLUMNS = ["primary_condition_category", "communication_language", "age_band", "gender",
                  "primary_support_goal", "support_orientation", "engagement_level",
                  "condition_duration_band"]


# =============================================================================
# REQUEST MODELS
# =============================================================================

class DatasetRequest(BaseModel):
    n: int = Field(ge=100, le=50000)
    seed: int = Field(ge=0, le=1_000_000)


class MatchingRequest(BaseModel):
    n: int = Field(ge=100, le=10000)
    seed: int = Field(ge=0, le=1_000_000)


class EvaluationRequest(BaseModel):
    n: int = Field(ge=300, le=5000)
    seed: int = Field(ge=0, le=1_000_000)
    replicates: int = Field(ge=5, le=30)


# =============================================================================
# FILE HELPERS
# =============================================================================

def _dataset_csv(n: int, seed: int) -> Path:
    path = paths.dataset_dir(n) / f"profiles_seed{seed}.csv"
    if not path.exists():
        raise HTTPException(404, f"No dataset with n={n}, seed={seed}. Generate it first.")
    return path


def _matching_json(n: int, seed: int) -> Path:
    path = paths.OUTPUT_DIR / "matching" / f"matching_n{n}_seed{seed}.json"
    if not path.exists():
        raise HTTPException(404, f"No matching run for n={n}, seed={seed}. Run matching first.")
    return path


@lru_cache(maxsize=8)
def _profiles_cached(path: str, mtime: float) -> pd.DataFrame:
    return load_profiles(path)


def _profiles(n: int, seed: int) -> pd.DataFrame:
    path = _dataset_csv(n, seed)
    return _profiles_cached(str(path), path.stat().st_mtime)


@lru_cache(maxsize=4)
def _matching_cached(path: str, mtime: float) -> dict:
    data = json.loads(Path(path).read_text())
    # Index: method -> profile_id -> group record (or None), for fast lookups.
    index = {}
    for method, outcome in data["methods"].items():
        index[method] = {pid: g for g in outcome["groups"] for pid in g["members"]}
    return {"data": data, "index": index}


def _matching(n: int, seed: int) -> dict:
    path = _matching_json(n, seed)
    return _matching_cached(str(path), path.stat().st_mtime)


def _records(df: pd.DataFrame) -> list:
    return json.loads(df.to_json(orient="records"))


# =============================================================================
# PAGES AND FILES
# =============================================================================

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/output/{relative:path}", include_in_schema=False)
def output_file(relative: str):
    """Figures and reports from output folder (read-only, no paths outside it)."""
    root = paths.OUTPUT_DIR.resolve()
    target = (root / relative).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(404, "File not found.")
    return FileResponse(target)


# =============================================================================
# STATE
# =============================================================================

@app.get("/api/state")
def state():
    """What exists in output: datasets, matching runs, evaluations."""
    out = paths.OUTPUT_DIR
    datasets = []
    for d in sorted(out.glob("n*")):
        if d.is_dir() and re.fullmatch(r"n\d+", d.name):
            for f in d.glob("profiles_seed*.csv"):
                datasets.append({"n": int(d.name[1:]),
                                 "seed": int(re.search(r"seed(\d+)", f.name).group(1))})
    runs = [{"n": int(m.group(1)), "seed": int(m.group(2))}
            for f in (out / "matching").glob("matching_n*_seed*.json")
            if (m := re.fullmatch(r"matching_n(\d+)_seed(\d+)\.json", f.name))]
    evaluations = sorted(int(m.group(1)) for f in (out / "evaluation").glob("evaluation_n*.json")
                         if (m := re.fullmatch(r"evaluation_n(\d+)\.json", f.name)))
    key = lambda x: (x["n"], x["seed"])
    return {"datasets": sorted(datasets, key=key), "matching_runs": sorted(runs, key=key),
            "evaluations": evaluations}


# =============================================================================
# DATASETS
# =============================================================================

@app.post("/api/datasets")
def create_dataset(req: DatasetRequest):
    """Generate a dataset with its validation report and figures."""
    outdir = paths.dataset_dir(req.n)
    df = generate_dataset(req.n, req.seed)
    save_dataset(df, str(outdir), req.seed, "csv")
    write_validation_report(df, req.seed, str(outdir / f"validation_report_seed{req.seed}.md"))
    generate_visualizations(df, str(outdir), req.seed)
    return {"n": req.n, "seed": req.seed, "consistency_violations": audit_consistency(df)["TOTAL"]}


@app.get("/api/datasets/{n}/{seed}/validation")
def validation(n: int, seed: int):
    df = _profiles(n, seed)
    chi = []
    for column, (targets, source) in CHI_SQUARE_TARGETS.items():
        table, statistic, p_value = _categorical_report(df, column, targets, len(df))
        chi.append({"attribute": column, "source": source, "statistic": statistic,
                    "p_value": p_value, "rows": _records(table)})
    base = f"/output/n{n}"
    return {
        "n": len(df), "seed": seed,
        "consistency": {k: int(v) for k, v in audit_consistency(df).items()},
        "chi_square": chi,
        "figures": [{"name": name, "label": label,
                     "url": f"{base}/profiles_seed{seed}_{name}.png"} for name, label in FIGURES],
        "report_url": f"{base}/validation_report_seed{seed}.md",
    }


@app.get("/api/datasets/{n}/{seed}/profiles")
def profiles(n: int, seed: int, request: Request, search: str = "", page: int = 1,
             page_size: int = 50):
    df = _profiles(n, seed)
    facets = {c: sorted(df[c].astype(str).unique().tolist()) for c in FILTER_COLUMNS}
    view = df
    for column in FILTER_COLUMNS:
        value = request.query_params.get(column)
        if value:
            view = view[view[column].astype(str) == value]
    if search:
        view = view[view["profile_id"].str.contains(search.strip(), case=False, regex=False)]
    page_size = max(1, min(page_size, 500))
    start = (max(page, 1) - 1) * page_size
    return {"total": len(view), "page": page, "page_size": page_size, "facets": facets,
            "rows": _records(view.iloc[start:start + page_size])}


# =============================================================================
# MATCHING
# =============================================================================

@app.post("/api/matching")
def create_matching(req: MatchingRequest):
    """Run every method on a dataset and save the result to output/matching."""
    df = _profiles(req.n, req.seed)
    run = run_all_methods(df, seed=req.seed)
    path = paths.OUTPUT_DIR / "matching" / f"matching_n{req.n}_seed{req.seed}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run_to_dict(run), indent=1, default=float))
    return {"n": req.n, "seed": req.seed,
            "seconds": {m: round(o.seconds, 2) for m, o in run.methods.items()}}


@app.get("/api/matching/{n}/{seed}")
def matching_summary(n: int, seed: int):
    data = _matching(n, seed)["data"]
    weighted = data["methods"]["weighted_gower"]
    groups_per_pool = {}
    for g in weighted["groups"]:
        key = (g["category"], g["language"])
        groups_per_pool[key] = groups_per_pool.get(key, 0) + 1
    pools = [{**p, "n_groups": groups_per_pool.get((p["category"], p["language"]), 0)}
             for p in data["hard_rules"]["pools"]]
    methods = {m: {"n_groups": o["n_groups"], "n_unmatched": o["n_unmatched"],
                   "seconds": o["seconds"],
                   "mean_score": float(np.mean([g["score"] for g in o["groups"]]))
                   if o["groups"] else None}
               for m, o in data["methods"].items()}
    return {"n": data["n_profiles"], "seed": data["seed"], "methods": methods,
            "rules": data["hard_rules"]["rules"], "pools": pools}


@app.get("/api/matching/{n}/{seed}/groups")
def matching_groups(n: int, seed: int, method: str, category: str, language: str):
    data = _matching(n, seed)["data"]
    if method not in data["methods"]:
        raise HTTPException(404, f"Unknown method {method}.")
    return [g for g in data["methods"][method]["groups"]
            if g["category"] == category and g["language"] == language]


@app.get("/api/matching/{n}/{seed}/unmatched")
def matching_unmatched(n: int, seed: int, method: str = "weighted_gower"):
    data = _matching(n, seed)["data"]
    if method not in data["methods"]:
        raise HTTPException(404, f"Unknown method {method}.")
    return data["methods"][method]["unmatched"]


@lru_cache(maxsize=32)
def _pool_map(n: int, seed: int, category: str, language: str, mtime: float) -> dict:
    df = _profiles(n, seed)
    pools, _ = partition_into_eligible_pools(df)
    if (category, language) not in pools:
        raise HTTPException(404, "No such pool.")
    pool = pools[(category, language)].reset_index(drop=True)
    coords = classical_mds(compute_gower_distance_matrix(pool, DEFAULT_WEIGHTS))
    return {"ids": pool["profile_id"].tolist(), "coords": coords.round(5).tolist()}


@app.get("/api/matching/{n}/{seed}/map")
def matching_map(n: int, seed: int, category: str, language: str):
    """2-D positions for one pool (classical MDS of the weighted Gower distances,
    for display only) with each profile's group under every method."""
    m = _matching(n, seed)
    csv = _dataset_csv(n, seed)
    base = _pool_map(n, seed, category, language, csv.stat().st_mtime)
    points = []
    for pid, (x, y) in zip(base["ids"], base["coords"]):
        groups = {method: (m["index"][method][pid]["group_id"] if pid in m["index"][method] else None)
                  for method in m["data"]["methods"]}
        points.append({"profile_id": pid, "x": x, "y": y, "group": groups})
    return {"category": category, "language": language, "points": points}


@app.get("/api/matching/{n}/{seed}/profiles/{profile_id}")
def matching_profile(n: int, seed: int, profile_id: str):
    df = _profiles(n, seed)
    row = df[df["profile_id"] == profile_id]
    if row.empty:
        raise HTTPException(404, f"No profile {profile_id}.")
    m = _matching(n, seed)
    methods = {}
    for method, outcome in m["data"]["methods"].items():
        group = m["index"][method].get(profile_id)
        if group:
            methods[method] = {"group_id": group["group_id"], "members": group["members"],
                               "score": group["score"], "explanation": group["explanation"]}
        else:
            reason = next((u for u in outcome["unmatched"] if u["profile_id"] == profile_id), None)
            methods[method] = {"group_id": None,
                               "reason": reason["plain_language"] if reason
                               else explain_unmatched("unknown")}
    return {"attributes": _records(row)[0], "methods": methods}


# =============================================================================
# EVALUATION
# =============================================================================

@app.get("/api/evaluation/{n}")
def evaluation(n: int):
    folder = paths.OUTPUT_DIR / "evaluation"
    results = folder / f"evaluation_n{n}.json"
    if not results.exists():
        raise HTTPException(404, f"No evaluation for n={n}. Run the evaluation first.")
    report = folder / f"evaluation_report_n{n}.md"
    return {"results": json.loads(results.read_text()),
            "report": report.read_text() if report.exists() else ""}


@app.post("/api/evaluation/run")
def run_evaluation(req: EvaluationRequest):
    if not JOB.start(req.n, req.seed, req.replicates):
        raise HTTPException(409, "An evaluation is already running.")
    return JOB.snapshot()


@app.get("/api/jobs/current")
def current_job():
    return JOB.snapshot()


@app.get("/api/methods")
def methods():
    return list(METHODS)
