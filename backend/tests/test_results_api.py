import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app

ROOT = Path(__file__).resolve().parents[2]


def test_results_are_served_from_the_exported_summary(tmp_path):
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"generated_at": "x", "finetuning": {"rows": []}}))
    client = TestClient(create_app(repos_root=ROOT, data_dir=tmp_path, results_file=summary))
    assert client.get("/results").json()["generated_at"] == "x"


def test_missing_summary_is_a_404(tmp_path):
    client = TestClient(create_app(repos_root=ROOT, data_dir=tmp_path, results_file=tmp_path / "nope.json"))
    assert client.get("/results").status_code == 404


def test_models_list_the_registry_with_measured_numbers(tmp_path):
    client = TestClient(create_app(repos_root=ROOT, data_dir=tmp_path))
    models = client.get("/models").json()
    ids = {m["id"] for m in models["models"]}
    assert {"ft-q8", "ft-q4", "ft-f16", "base-q4"} <= ids
    q8 = next(m for m in models["models"] if m["id"] == "ft-q8")
    assert q8["hf_repo"].startswith("MedGm/Llama-Locali") and q8["laptop"]["humaneval_plus"]["score"] == 63.2
    assert q8["peak_ram_gb"] == 1.79


def test_the_fine_tuned_3b_is_the_default_and_does_not_borrow_the_1_5b_measurements(tmp_path):
    client = TestClient(create_app(repos_root=ROOT, data_dir=tmp_path))
    models = {m["id"]: m for m in client.get("/models").json()["models"]}
    ft3b = models["ft3b-q4"]
    assert ft3b["recommended"] == "default" and ft3b["laptop"] == {} and ft3b["peak_ram_gb"] is None
    assert any("HumanEvalFix" in h for h in ft3b["highlights"])
    assert [m["id"] for m in models.values() if m["recommended"] == "default"] == ["ft3b-q4"]
    assert models["ft-q4"]["laptop"]  # the 1.5B entries keep their ladder numbers
