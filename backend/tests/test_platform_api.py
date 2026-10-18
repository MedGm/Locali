import json
import os
import subprocess

from fastapi.testclient import TestClient

from backend.app import create_app


def make_repos(tmp_path):
    root = tmp_path / "repos"
    (root / "shop" / "shop").mkdir(parents=True)
    (root / "shop" / "shop" / "cart.py").write_text("def total(xs):\n    return sum(xs)\n")
    (root / "notes").mkdir()
    (root / "notes" / "README.md").write_text("no code here\n")
    (root / ".hidden").mkdir()
    (root / ".hidden" / "x.py").write_text("x = 1\n")
    git = ["git", "-C", str(root / "shop"), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", str(root / "shop")], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "first commit"], check=True)
    return root


def save_run(data, run):
    (data / "runs").mkdir(parents=True, exist_ok=True)
    (data / "runs" / f"{run['id']}.json").write_text(json.dumps(run))


def finding(category, severity="medium", tool="bandit"):
    return {"category": category, "severity": severity, "tool": tool, "path": "a.py", "line": 1, "message": "m"}


def test_repos_lists_code_folders_with_git_and_run_info(tmp_path):
    root, data = make_repos(tmp_path), tmp_path / "data"
    save_run(data, {"id": "r1", "repo": "shop", "mode": "agents", "status": "done", "created": "2026-10-01T10:00:00Z",
                    "findings": [], "patches": [], "devops": {"ready_to_merge": False}})
    save_run(data, {"id": "r2", "repo": "shop", "mode": "analyze", "status": "done", "created": "2026-10-02T10:00:00Z",
                    "findings": []})
    repos = TestClient(create_app(repos_root=root, data_dir=data)).get("/repos").json()
    assert [r["name"] for r in repos] == ["shop"]
    shop = repos[0]
    assert shop["python_files"] == 1 and shop["git"]["last_commit"] == "first commit"
    assert shop["runs"] == 2 and shop["last_run"]["id"] == "r2"
    assert shop["ready_to_merge"] is False  # from the latest agent run
    assert shop["open_patches"] == 0


def test_new_runs_record_when_they_were_created(tmp_path):
    root = make_repos(tmp_path)
    run = TestClient(create_app(repos_root=root, data_dir=tmp_path / "data")).post("/runs", json={"repo": "shop"}).json()
    assert run["created"].endswith("Z") and run["created"][:4].isdigit()


def test_trends_are_ordered_by_time_and_count_findings(tmp_path):
    root, data = make_repos(tmp_path), tmp_path / "data"
    save_run(data, {"id": "b", "repo": "shop", "mode": "agents", "status": "done", "created": "2026-10-03T00:00:00Z",
                    "findings": [finding("bug", tool="model")], "patches": [{"ok": True}, {"ok": False}],
                    "tests_before": {"passed": 4, "failed": ["t"], "coverage_percent": 41.5},
                    "devops": {"ready_to_merge": False}})
    save_run(data, {"id": "a", "repo": "shop", "mode": "analyze", "status": "done", "created": "2026-10-01T00:00:00Z",
                    "findings": [finding("security", "high"), finding("security"), finding("quality")]})
    save_run(data, {"id": "c", "repo": "other", "mode": "analyze", "status": "done", "created": "2026-10-02T00:00:00Z",
                    "findings": []})
    save_run(data, {"id": "d", "repo": "shop", "mode": "agents", "status": "failed", "created": "2026-10-04T00:00:00Z"})
    points = TestClient(create_app(repos_root=root, data_dir=data)).get("/trends", params={"repo": "shop"}).json()
    assert [p["id"] for p in points] == ["a", "b"]  # failed runs have nothing to plot
    assert points[0]["findings"] == {"bug": 0, "security": 2, "quality": 1} and points[0]["high_security"] == 1
    assert points[0]["tests_passed"] is None
    assert points[1]["tests_passed"] == 4 and points[1]["tests_failed"] == 1 and points[1]["coverage_percent"] == 41.5
    assert points[1]["patches"] == 2 and points[1]["patches_validated"] == 1 and points[1]["ready_to_merge"] is False


def test_settings_show_configuration_but_never_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALI_MODEL_URL", "http://user:hunter2@127.0.0.1:8080/v1")
    monkeypatch.setenv("LOCALI_MODEL_KEY", "sk-secret-value-123")
    monkeypatch.setenv("LOCALI_MODEL_ID", "ft-q8")
    root = make_repos(tmp_path)
    c = TestClient(create_app(repos_root=root, data_dir=tmp_path / "data", model=lambda m: "x", api_token="tok-abc"))
    s = c.get("/settings", headers={"Authorization": "Bearer tok-abc"}).json()
    text = json.dumps(s)
    assert "hunter2" not in text and "sk-secret-value-123" not in text and "tok-abc" not in text
    assert s["model"]["url"] == "http://127.0.0.1:8080/v1" and s["model"]["key_set"] is True
    assert s["model"]["id"] == "ft-q8" and s["api_token_set"] is True
    assert s["repos_root"] == str(root.resolve()) and "devops" in s["workflow"]["steps"]
    assert all("env" in item for item in s["variables"])
    assert os.environ["LOCALI_MODEL_KEY"]  # untouched


def test_a_run_from_before_timestamps_gets_its_file_time(tmp_path):
    root, data = make_repos(tmp_path), tmp_path / "data"
    save_run(data, {"id": "old", "repo": "shop", "mode": "analyze", "status": "done", "findings": []})
    run = TestClient(create_app(repos_root=root, data_dir=data)).get("/runs/old").json()
    assert run["created"].endswith("Z")
