import json
import re
from pathlib import Path

from backend.agents.workflow import _report, change_groups, run_workflow
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
    if prompt.startswith("Write pytest integration tests"):
        name, module = re.search(r"for `(\w+)` in `([\w.]+)`", prompt).groups()
        return f"```python\nfrom {module} import {name}\n\n\ndef test_{name}_integration():\n    assert callable({name})\n```"
    if prompt.startswith("Write pytest tests for the HTTP endpoint"):
        module, factory = re.search(r"app in `([\w.]+)`. Build the app with `from [\w.]+ import (\w+)`", prompt).groups()
        return (f"```python\nfrom {module} import {factory}\n\n\ndef test_app_builds(tmp_path):\n"
                f"    assert {factory}(tmp_path / 'test.db') is not None\n```")
    if prompt.startswith("The following Python function has a bug"):
        return GOOD_FIX
    if prompt.startswith("Write a one-line docstring"):
        return "Does what the name says."
    raise AssertionError(f"unexpected prompt: {prompt[:80]}")


@needs_docker
def test_workflow_proposes_one_validated_patch_per_change_and_leaves_the_repo_alone(tmp_path):
    before = {p: p.read_bytes() for p in DEMO.rglob("*") if p.is_file()}
    store = PatchStore(tmp_path / "data")
    state = run_workflow(DEMO, run_id="run1", model=fake_model, store=store)

    assert [s for s in state["steps"]] == ["prepare", "analyze", "review", "testgen", "debug", "docs", "propose", "devops", "report"]
    assert state["tests_by_kind"]["integration"] and state["tests_by_kind"]["api"] and state["tests_by_kind"]["unit"]
    assert sorted(f for files in state["tests_by_kind"].values() for f in files) == sorted(state["tests_added"])
    assert {f["tool"] for f in state["findings"]} >= {"bandit", "semgrep", "secrets"}
    assert [f["test"] for f in state["fixes"] if f["fixed"]] == ["tests/test_pricing.py::test_discount"]

    patches = [store.get(i) for i in state["patch_ids"]]
    fixes = [p for p in patches if p.kind == "fix"]
    tests = [p for p in patches if p.kind == "tests"]
    docs = [p for p in patches if p.kind == "docs"]
    assert [p.files for p in fixes] == [["tinyshop/pricing.py"]]
    assert tests and all(len(p.files) == 1 and p.files[0].startswith("tests/test_locali_") for p in tests)
    assert docs and all(len(p.files) == 1 and p.files[0] != "tinyshop/pricing.py" for p in docs)
    assert len(patches) == len(fixes) + len(tests) + len(docs)
    assert all(p.status == "proposed" and p.validation["ok"] and p.title for p in patches)
    assert "## Fixes" in state["report"] and "test_discount" in state["report"]
    assert [r["name"] for r in state["devops"]["dependencies"]] == ["reqeusts"]
    assert state["devops"]["ready_to_merge"] is False and "## DevOps summary" in state["report"]

    assert {p: p.read_bytes() for p in DEMO.rglob("*") if p.is_file()} == before
    assert not Path(state["workspace"]).exists()


@needs_docker
def test_workflow_without_tools_keeps_only_model_findings(tmp_path):
    state = run_workflow(DEMO, run_id="run2", model=fake_model, store=PatchStore(tmp_path / "data"), tools=False)
    assert "analyze" not in state["steps"]
    assert all(f["tool"] == "model" for f in state["findings"])
    assert state["patch_ids"]


def test_on_step_reports_each_step_before_it_runs(tmp_path):
    seen = []

    def stop_after_prepare(messages):
        raise RuntimeError("stop")

    import pytest
    with pytest.raises(RuntimeError):
        run_workflow(DEMO, run_id="run3", model=stop_after_prepare, store=PatchStore(tmp_path / "data"),
                     tools=False, on_step=lambda name, state: seen.append(name))
    assert seen == ["prepare", "review"]


@needs_docker
def test_no_tests_are_generated_for_functions_with_security_findings(tmp_path):
    asked = []

    def recording_model(messages):
        prompt = messages[-1]["content"]
        if prompt.startswith("Write pytest unit tests"):
            asked.append(re.search(r"function `(\w+)`", prompt).group(1))
        return fake_model(messages)

    run_workflow(DEMO, run_id="run4", model=recording_model, store=PatchStore(tmp_path / "data"))
    flagged = {"hash_password", "load_session", "main", "find_products", "export_report"}
    assert asked and not flagged & set(asked)
    assert {"total_units", "bulk_discount", "needs_restock"} <= set(asked)


def test_patch_titles_name_the_kind_of_test():
    state = {"tests_added": ["tests/test_locali_bulk_discount.py", "tests/test_locali_integration_daily_report.py",
                             "tests/test_locali_api_place_order.py"]}
    titles = [title for _, kind, title in change_groups(state, []) if kind == "tests"]
    assert titles == ["Regression tests for bulk_discount (they record what the code does now)",
                      "Integration tests for daily_report", "API tests for place_order"]


def test_report_groups_tests_by_kind():
    state = {"run_id": "r", "findings": [], "review_dropped": 0, "suspects": [], "fixes": [], "patches": [],
             "tests_added": ["tests/test_locali_api_place_order.py"],
             "tests_by_kind": {"unit": [], "integration": [], "api": ["tests/test_locali_api_place_order.py"]}}
    report = _report(state)
    tests = report.split("## Tests added")[1].split("## Suspected")[0]
    assert "Unit: none" in tests and "Integration: none" in tests
    assert "API:\n- tests/test_locali_api_place_order.py" in tests
