"""FastAPI backend: datasets, validation, profiles, matching, map, evaluation."""

import json

import pytest
from fastapi.testclient import TestClient

import paths
from api.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path)
    return TestClient(app)


def generate(client, n=300, seed=5):
    r = client.post("/api/datasets", json={"n": n, "seed": seed})
    assert r.status_code == 200, r.text
    return r.json()


def test_index_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "<title>" in r.text


def test_state_is_empty_before_anything_is_generated(client):
    state = client.get("/api/state").json()
    assert state == {"datasets": [], "matching_runs": [], "evaluations": [], "read_only": False}


def test_generate_dataset_writes_to_output_and_is_listed(client, tmp_path):
    generate(client)
    assert (tmp_path / "n300" / "profiles_seed5.csv").exists()
    state = client.get("/api/state").json()
    assert state["datasets"] == [{"n": 300, "seed": 5}]


def test_dataset_size_is_bounded(client):
    assert client.post("/api/datasets", json={"n": 10, "seed": 1}).status_code == 422


def test_validation_summary(client):
    generate(client)
    v = client.get("/api/datasets/300/5/validation").json()
    assert v["consistency"]["TOTAL"] == 0
    assert {c["attribute"] for c in v["chi_square"]} == {
        "communication_language", "gender", "age_band"}
    assert all(0 <= c["p_value"] <= 1 for c in v["chi_square"])
    assert len(v["figures"]) == 8
    assert client.get(v["figures"][0]["url"]).status_code == 200


def test_profiles_are_filtered_and_paged(client):
    generate(client)
    page = client.get("/api/datasets/300/5/profiles", params={"page_size": 10}).json()
    assert page["total"] == 300 and len(page["rows"]) == 10
    cat = page["facets"]["primary_condition_category"][0]
    filtered = client.get("/api/datasets/300/5/profiles",
                          params={"primary_condition_category": cat}).json()
    assert all(r["primary_condition_category"] == cat for r in filtered["rows"])
    one = client.get("/api/datasets/300/5/profiles", params={"search": "P000007"}).json()
    assert [r["profile_id"] for r in one["rows"]] == ["P000007"]


def test_missing_dataset_says_how_to_create_it(client):
    r = client.get("/api/datasets/300/99/validation")
    assert r.status_code == 404
    assert "Generate" in r.json()["detail"]


def test_matching_run_summary_groups_map_and_profile(client):
    generate(client)
    r = client.post("/api/matching", json={"n": 300, "seed": 5})
    assert r.status_code == 200, r.text
    summary = client.get("/api/matching/300/5").json()
    assert set(summary["methods"]) == {"weighted_gower", "unweighted_gower", "single_age_band",
                                       "single_primary_support_goal", "random"}
    pool = next(p for p in summary["pools"] if p["n_groups"] >= 2)

    groups = client.get("/api/matching/300/5/groups", params={
        "method": "weighted_gower", "category": pool["category"],
        "language": pool["language"]}).json()
    assert len(groups) == pool["n_groups"]
    assert "summary" in groups[0]["explanation"]

    m = client.get("/api/matching/300/5/map", params={
        "category": pool["category"], "language": pool["language"]}).json()
    assert len(m["points"]) == pool["size"]
    assert set(m["points"][0]["group"]) == set(summary["methods"])

    pid = groups[0]["members"][0]
    profile = client.get(f"/api/matching/300/5/profiles/{pid}").json()
    assert profile["attributes"]["profile_id"] == pid
    assert profile["methods"]["weighted_gower"]["group_id"] == groups[0]["group_id"]


def test_matching_without_dataset_is_404(client):
    r = client.post("/api/matching", json={"n": 300, "seed": 5})
    assert r.status_code == 404


def test_matching_size_is_bounded(client):
    assert client.post("/api/matching", json={"n": 20000, "seed": 1}).status_code == 422


def test_evaluation_results_are_served(client, tmp_path):
    (tmp_path / "evaluation").mkdir()
    (tmp_path / "evaluation" / "evaluation_n300.json").write_text(json.dumps({"n": 300}))
    (tmp_path / "evaluation" / "evaluation_report_n300.md").write_text("# Report")
    assert client.get("/api/state").json()["evaluations"] == [300]
    ev = client.get("/api/evaluation/300").json()
    assert ev["results"] == {"n": 300} and ev["report"] == "# Report"
    assert client.get("/api/evaluation/999").status_code == 404


def test_evaluation_job_is_idle_until_started(client):
    assert client.get("/api/jobs/current").json()["status"] == "idle"
    assert client.post("/api/evaluation/run",
                       json={"n": 50, "seed": 1, "replicates": 20}).status_code == 422


@pytest.fixture
def read_only_client(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("READ_ONLY", "1")
    return TestClient(app)


def test_read_only_mode_blocks_every_change(read_only_client):
    assert read_only_client.get("/api/state").json()["read_only"] is True
    for url, body in [("/api/datasets", {"n": 300, "seed": 5}),
                      ("/api/matching", {"n": 300, "seed": 5}),
                      ("/api/evaluation/run", {"n": 300, "seed": 5, "replicates": 5})]:
        r = read_only_client.post(url, json=body)
        assert r.status_code == 403, url
        assert "view-only" in r.json()["detail"]
