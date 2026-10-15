import json

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.patches import propose
from backend.workspace import open_workspace


def ok(path, files):
    return {"ok": True}


@pytest.fixture
def env(tmp_path):
    repos = tmp_path / "repos"
    repo = repos / "shop"
    repo.mkdir(parents=True)
    (repo / "app.py").write_text("def add(a, b):\n    return a - b\n")
    data = tmp_path / "data"
    app = create_app(repos_root=repos, data_dir=data, validate=ok)
    client = TestClient(app)
    ws = open_workspace(repo)
    (ws.path / "app.py").write_text("def add(a, b):\n    return a + b\n")
    patch = propose(ws, run_id="run1", validate=ok, store=app.state.patches)
    ws.cleanup()
    return client, repo, data, patch


def decision(patch, **over):
    return {"sha256": patch.sha256, "baseline": patch.baseline, "reviewer": "medgm", **over}


def test_patch_is_listed_and_inspectable(env):
    client, _, _, patch = env
    assert [p["id"] for p in client.get("/runs/run1/patches").json()] == [patch.id]
    body = client.get(f"/patches/{patch.id}").json()
    assert body["diff"] == patch.diff and body["validation"] == {"ok": True} and body["status"] == "proposed"


def test_approve_with_wrong_hash_is_refused(env):
    client, repo, _, patch = env
    r = client.post(f"/patches/{patch.id}/approve", json=decision(patch, sha256="0" * 64))
    assert r.status_code == 409
    assert client.post(f"/patches/{patch.id}/apply").status_code == 409
    assert "a - b" in (repo / "app.py").read_text()


def test_approve_apply_revert_round_trip_is_audited(env):
    client, repo, data, patch = env
    assert client.post(f"/patches/{patch.id}/approve", json=decision(patch)).json()["status"] == "approved"
    assert client.post(f"/patches/{patch.id}/apply").json()["status"] == "applied"
    assert "a + b" in (repo / "app.py").read_text()
    assert client.post(f"/patches/{patch.id}/revert").json()["status"] == "reverted"
    assert "a - b" in (repo / "app.py").read_text()
    actions = [json.loads(line)["action"] for line in (data / "audit.jsonl").read_text().splitlines()]
    assert actions == ["patch.proposed", "patch.approved", "patch.applied", "patch.reverted"]


def test_stale_patch_can_be_revalidated_into_a_new_proposal(env):
    client, repo, _, patch = env
    client.post(f"/patches/{patch.id}/approve", json=decision(patch))
    (repo / "app.py").write_text("# header\ndef add(a, b):\n    return a - b\n")
    assert client.post(f"/patches/{patch.id}/apply").status_code == 409
    assert client.get(f"/patches/{patch.id}").json()["status"] == "stale"

    new = client.post(f"/patches/{patch.id}/revalidate").json()
    assert new["id"] != patch.id and new["status"] == "proposed"
    assert new["baseline"]["app.py"] != patch.baseline["app.py"]
    assert "# header" not in new["diff"].split("@@")[0]
    client.post(f"/patches/{new['id']}/approve", json={"sha256": new["sha256"], "baseline": new["baseline"],
                                                       "reviewer": "medgm"})
    assert client.post(f"/patches/{new['id']}/apply").json()["status"] == "applied"
    assert (repo / "app.py").read_text() == "# header\ndef add(a, b):\n    return a + b\n"


def test_reject_and_unknown_patch(env):
    client, _, _, patch = env
    assert client.post(f"/patches/{patch.id}/reject", json={"reviewer": "medgm"}).json()["status"] == "rejected"
    assert client.post(f"/patches/{patch.id}/approve", json=decision(patch)).status_code == 409
    assert client.get("/patches/nope").status_code == 404


def test_revalidation_refuses_a_patch_that_no_longer_fits(env):
    client, repo, _, patch = env
    client.post(f"/patches/{patch.id}/approve", json=decision(patch))
    (repo / "app.py").write_text("def multiply(x, y):\n    return x * y\n")
    client.post(f"/patches/{patch.id}/apply")
    r = client.post(f"/patches/{patch.id}/revalidate")
    assert r.status_code == 409 and "no longer applies" in r.json()["detail"]
    assert (repo / "app.py").read_text() == "def multiply(x, y):\n    return x * y\n"
