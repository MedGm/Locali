import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.tests.test_workflow import fake_model
from evaluation.tests.test_codegen import needs_docker

ROOT = Path(__file__).resolve().parents[2]


def wait_for(client, run_id, timeout_s=600):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        run = client.get(f"/runs/{run_id}").json()
        if run["status"] in ("done", "failed"):
            return run
        time.sleep(1)
    raise TimeoutError(run_id)


def test_agent_mode_without_a_model_is_refused(tmp_path):
    client = TestClient(create_app(repos_root=ROOT, data_dir=tmp_path))
    assert client.post("/runs", json={"repo": "demo_repo", "mode": "agents"}).status_code == 503


def test_unknown_mode_is_rejected(tmp_path):
    client = TestClient(create_app(repos_root=ROOT, data_dir=tmp_path, model=fake_model))
    assert client.post("/runs", json={"repo": "demo_repo", "mode": "yolo"}).status_code == 422


@needs_docker
def test_agent_run_happens_in_the_background_and_ends_with_a_patch(tmp_path):
    before = {p: p.read_bytes() for p in (ROOT / "demo_repo").rglob("*") if p.is_file()}
    client = TestClient(create_app(repos_root=ROOT, data_dir=tmp_path, model=fake_model))
    r = client.post("/runs", json={"repo": "demo_repo", "mode": "agents"})
    assert r.status_code == 202 and r.json()["status"] in ("queued", "running")

    run = wait_for(client, r.json()["id"])
    assert run["status"] == "done", run.get("error")
    assert "## Fixes" in run["report"] and run["patch_id"]
    assert [p["id"] for p in client.get(f"/runs/{run['id']}/patches").json()] == [run["patch_id"]]
    assert {p: p.read_bytes() for p in (ROOT / "demo_repo").rglob("*") if p.is_file()} == before

    actions = [json.loads(line)["action"] for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert actions[0] == "run.created" and "run.started" in actions and actions[-1] == "run.finished"


@pytest.mark.parametrize("repo", ["demo_repo"])
def test_failing_agent_run_is_reported_and_cleans_up(tmp_path, repo):
    def broken_model(messages):
        raise RuntimeError("model server down")

    client = TestClient(create_app(repos_root=ROOT, data_dir=tmp_path, model=broken_model, tools=False))
    run = wait_for(client, client.post("/runs", json={"repo": repo, "mode": "agents"}).json()["id"])
    assert run["status"] == "failed" and "model server down" in run["error"]
    leftovers = [p for p in Path("/tmp").glob("locali-ws-*") if p.stat().st_mtime > time.time() - 60]
    assert leftovers == []
