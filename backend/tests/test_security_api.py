import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.agents.model import guarded
from backend.app import create_app
from security.commands import CommandNotAllowed, run

ROOT = Path(__file__).resolve().parents[2]
KEY = "AKIA" + "IOSFODNN7EXAMPLE"


@pytest.fixture
def app_and_client(tmp_path):
    app = create_app(repos_root=ROOT, data_dir=tmp_path, api_token="t0ken")
    return app, TestClient(app, headers={"Authorization": "Bearer t0ken"}), tmp_path


def test_audit_log_is_listed_newest_first_and_filterable(app_and_client):
    _, client, _ = app_and_client
    client.post("/runs", json={"repo": "demo_repo"})
    client.post("/runs", json={"repo": "/etc"})
    events = client.get("/audit").json()
    assert [e["action"] for e in events][:3] == ["run.refused", "run.finished", "run.created"]
    assert [e["action"] for e in client.get("/audit?action=run.refused").json()] == ["run.refused"]
    assert len(client.get("/audit?limit=1").json()) == 1


def test_security_events_collect_refusals_blocked_commands_and_redactions(app_and_client):
    _, client, _ = app_and_client
    TestClient(client.app).get("/runs")  # no token
    client.post("/runs", json={"repo": "../"})
    with pytest.raises(CommandNotAllowed):
        run(["curl", "http://setup.tinyshop-tools.example"])
    events = client.get("/security/events").json()
    kinds = [e["action"] for e in events["events"]]
    assert {"auth.refused", "run.refused", "command.refused"} <= set(kinds)
    assert events["counts"]["command.refused"] == 1
    assert "curl" in json.dumps(events["events"])


def test_the_model_guard_reports_how_much_it_redacted():
    log = []
    model = guarded(lambda msgs: "ok", log.append, step=lambda: "debug")
    model([{"role": "user", "content": f'a = "{KEY}"\nb = "{KEY}"'}])
    assert log[0]["redactions"] == 2
