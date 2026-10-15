from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app

ROOT = Path(__file__).resolve().parents[2]


def client(tmp_path, token="s3cret-token"):
    return TestClient(create_app(repos_root=ROOT, data_dir=tmp_path, api_token=token))


def test_health_is_open(tmp_path):
    assert client(tmp_path).get("/health").status_code == 200


def test_requests_without_the_token_are_refused(tmp_path):
    c = client(tmp_path)
    assert c.get("/runs/abc").status_code == 401
    assert c.post("/runs", json={"repo": "demo_repo"}).status_code == 401
    assert c.get("/runs/abc", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_requests_with_the_token_pass(tmp_path):
    c = client(tmp_path)
    assert c.get("/runs/abc", headers={"Authorization": "Bearer s3cret-token"}).status_code == 404


def test_refusals_are_audited_without_the_token_value(tmp_path):
    c = client(tmp_path)
    c.get("/runs/abc", headers={"Authorization": "Bearer guess"})
    log = (tmp_path / "audit.jsonl").read_text()
    assert "auth.refused" in log and "guess" not in log
