from pathlib import Path

import mlflow
from fastapi.testclient import TestClient
from mlflow import MlflowClient

from backend.app import create_app
from backend.tests.test_agent_api import wait_for
from backend.tests.test_workflow import fake_model
from evaluation.tests.test_codegen import needs_docker

ROOT = Path(__file__).resolve().parents[2]


@needs_docker
def test_agent_runs_are_logged_to_mlflow_with_a_trace(tmp_path):
    uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    client = TestClient(create_app(repos_root=ROOT, data_dir=tmp_path / "data", model=fake_model,
                                   mlflow_uri=uri, mlflow_artifacts=str(tmp_path / "artifacts")))
    run_id = client.post("/runs", json={"repo": "demo_repo", "mode": "agents"}).json()["id"]
    assert wait_for(client, run_id)["status"] == "done"

    mlflow.set_tracking_uri(uri)
    ml = MlflowClient(uri)
    [exp] = [e for e in ml.search_experiments() if e.name == "agent-runs"]
    [run] = ml.search_runs([exp.experiment_id])
    assert run.data.tags["mlflow.runName"] == run_id
    assert run.data.params["repo"] == "demo_repo" and run.data.params["mode"] == "agents"
    assert run.data.metrics["findings_security"] >= 5 and run.data.metrics["fixes_fixed"] == 1
    assert run.data.metrics["model_calls"] > 0 and run.data.metrics["patches"] >= 1
    assert {a.path for a in ml.list_artifacts(run.info.run_id)} >= {"report.md", "trajectory.jsonl"}

    mlflow.flush_trace_async_logging()
    traces = mlflow.search_traces(locations=[exp.experiment_id], return_type="list", include_spans=True)
    assert len(traces) == 1
    names = [s.name for s in traces[0].data.spans]
    assert "agent_run" in names and {"review", "testgen", "debug"} <= set(names)
    calls = [s for s in traces[0].data.spans if s.name == "model_call"]
    assert calls and all("prompt" in s.inputs and s.outputs for s in calls)


def test_tracking_is_off_without_a_uri(tmp_path):
    app = create_app(repos_root=ROOT, data_dir=tmp_path, model=fake_model)
    assert app.state.tracker.enabled is False
