import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(tmp_path):
    app = create_app(repos_root=ROOT, data_dir=tmp_path)
    return TestClient(app), tmp_path


def test_health(client):
    c, _ = client
    assert c.get("/health").json() == {"status": "ok"}


def test_run_on_demo_repo_returns_findings_without_secret_values(client):
    c, _ = client
    r = c.post("/runs", json={"repo": "demo_repo"})
    assert r.status_code == 201
    run = r.json()
    assert run["status"] == "done"
    tools = {f["tool"] for f in run["findings"]}
    assert {"bandit", "semgrep", "secrets"} <= tools
    assert any(f["path"] == "tinyshop/settings.py" and f["tool"] == "secrets" for f in run["findings"])
    body = r.text
    assert "AKIAIOSFODNN7EXAMPLE" not in body and "wJalrXUtnFEMI" not in body

    again = c.get(f"/runs/{run['id']}")
    assert again.status_code == 200 and again.json() == run


def test_summary_counts_by_category(client):
    c, _ = client
    run = c.post("/runs", json={"repo": "demo_repo"}).json()
    counts = run["summary"]["by_category"]
    assert counts["security"] >= 5
    assert sum(counts.values()) == len(run["findings"])


@pytest.mark.parametrize("repo", ["../", "/etc", "demo_repo/../../", "does-not-exist"])
def test_repos_outside_the_root_or_missing_are_refused(client, repo):
    c, _ = client
    assert c.post("/runs", json={"repo": repo}).status_code in (400, 404)


def test_unknown_run_is_404(client):
    c, _ = client
    assert c.get("/runs/nope").status_code == 404


def test_actions_are_audited(client):
    c, data = client
    run = c.post("/runs", json={"repo": "demo_repo"}).json()
    c.post("/runs", json={"repo": "/etc"})
    events = [json.loads(line) for line in (data / "audit.jsonl").read_text().splitlines()]
    assert [e["action"] for e in events] == ["run.created", "run.finished", "run.refused"]
    assert events[1]["run_id"] == run["id"]
    assert all("time" in e for e in events)
