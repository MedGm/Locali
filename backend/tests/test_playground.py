import json

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.playground import TASKS, build_messages
from evaluation.client import Completion

CODE = "def add(a, b):\n    return a - b\n"


def test_python_presets_use_the_trained_formats():
    review = build_messages("review", "python", code=CODE)[-1]["content"]
    assert review.startswith("Review the following Python code") and '"findings"' in review
    tests = build_messages("tests", "python", code=CODE)[-1]["content"]
    assert "from solution import add" in tests
    fix = build_messages("fix", "python", code=CODE, test="def test_add():\n    assert add(1, 2) == 3",
                         error="assert -1 == 3")[-1]["content"]
    assert fix.startswith("The following Python function has a bug") and "assert -1 == 3" in fix


def test_other_languages_get_plain_instructions():
    review = build_messages("review", "javascript", code="function add(a, b) { return a - b }")[-1]["content"]
    assert "JavaScript" in review and "```javascript" in review
    tests = build_messages("tests", "go", code="func Add(a, b int) int { return a - b }")[-1]["content"]
    assert "Go" in tests and "testing" in tests


def test_free_prompt_needs_text_and_unknown_tasks_are_refused():
    with pytest.raises(ValueError):
        build_messages("free", "python", prompt="  ")
    with pytest.raises(ValueError):
        build_messages("nope", "python", code=CODE)
    assert set(TASKS) == {"review", "tests", "fix", "explain", "free"}


def fake_stream(answer):
    seen = []

    def model(messages, on_token):
        seen.append(messages)
        for piece in answer.split(" "):
            on_token(piece + " ")
        return Completion(answer, "", 12, len(answer.split()), 0.05, 0.2, "stop")
    return model, seen


def events(response):
    return [json.loads(line[6:]) for line in response.iter_lines() if line.startswith("data: ")]


def test_playground_streams_tokens_then_a_redacted_answer_and_logs_the_call(tmp_path):
    key = "AKIAIOSFODNN7EXAMPLE"
    model, seen = fake_stream(f"The key {key} is hard-coded here")
    app = create_app(repos_root=tmp_path, data_dir=tmp_path / "data", playground={"main": ("ft-q8", model)})
    client = TestClient(app)
    with client.stream("POST", "/playground", json={"task": "explain", "language": "python",
                                                     "code": f'KEY = "{key}"\n', "model": "main"}) as r:
        got = events(r)
    assert key not in json.dumps(seen)  # the model never saw it
    assert [e["type"] for e in got[:-1]] == ["token"] * (len(got) - 1)
    done = got[-1]
    assert done["type"] == "done" and key not in done["answer"] and "[REDACTED" in done["answer"]
    assert done["output_tokens"] > 0 and done["model"] == "ft-q8"
    log = (tmp_path / "data" / "audit.jsonl").read_text()
    assert '"playground.call"' in log and key not in log


def test_playground_models_and_errors(tmp_path):
    model, _ = fake_stream("ok")
    app = create_app(repos_root=tmp_path, data_dir=tmp_path / "data",
                     playground={"main": ("ft-q8", model), "compare": ("base-q4", model)})
    client = TestClient(app)
    assert client.get("/playground/models").json() == [{"key": "main", "id": "ft-q8"}, {"key": "compare", "id": "base-q4"}]
    assert client.post("/playground", json={"task": "explain", "language": "python", "code": "x", "model": "other"}).status_code == 404
    assert client.post("/playground", json={"task": "free", "language": "python", "prompt": ""}).status_code == 422
    bare = TestClient(create_app(repos_root=tmp_path, data_dir=tmp_path / "data2"))
    assert bare.get("/playground/models").json() == []
