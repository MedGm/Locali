import json
import re
from pathlib import Path

from backend.agents.workflow import run_workflow
from backend.patches import PatchStore
from backend.tests.test_debug_agent import GOOD_FIX
from evaluation.tests.test_codegen import needs_docker

DEMO = Path(__file__).resolve().parents[2] / "demo_repo"


def fake_model(messages):
    prompt = messages[-1]["content"]
    if prompt.startswith("Review the following"):
        return json.dumps({"findings": []})
    if prompt.startswith("Write pytest unit tests"):
        name = re.search(r"function `(\w+)`", prompt).group(1)
        return f"```python\nfrom solution import {name}\n\n\ndef test_{name}_exists():\n    assert callable({name})\n```"
    if prompt.startswith("The following Python function has a bug"):
        return GOOD_FIX
    raise AssertionError(f"unexpected prompt: {prompt[:80]}")


@needs_docker
def test_workflow_ends_in_one_validated_patch_and_leaves_the_repo_alone(tmp_path):
    before = {p: p.read_bytes() for p in DEMO.rglob("*") if p.is_file()}
    store = PatchStore(tmp_path / "data")
    state = run_workflow(DEMO, run_id="run1", model=fake_model, store=store)

    assert [s for s in state["steps"]] == ["prepare", "analyze", "review", "testgen", "debug", "propose", "report"]
    assert {f["tool"] for f in state["findings"]} >= {"bandit", "semgrep", "secrets"}
    assert [f["test"] for f in state["fixes"] if f["fixed"]] == ["tests/test_pricing.py::test_discount"]

    patch = store.get(state["patch_id"])
    assert patch.status == "proposed" and patch.validation["ok"]
    assert "tinyshop/pricing.py" in patch.files and any(f.startswith("tests/test_locali_") for f in patch.files)
    assert "## Fixes" in state["report"] and "test_discount" in state["report"]

    assert {p: p.read_bytes() for p in DEMO.rglob("*") if p.is_file()} == before
    assert not Path(state["workspace"]).exists()


@needs_docker
def test_workflow_without_tools_keeps_only_model_findings(tmp_path):
    state = run_workflow(DEMO, run_id="run2", model=fake_model, store=PatchStore(tmp_path / "data"), tools=False)
    assert "analyze" not in state["steps"]
    assert all(f["tool"] == "model" for f in state["findings"])
    assert state["patch_id"]
