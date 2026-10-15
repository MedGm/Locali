import json
from pathlib import Path

import pytest

from backend.agents.debug import debug_failing_tests, replace_function, target_of_test
from backend.workspace import open_workspace
from evaluation.tests.test_codegen import needs_docker

DEMO = Path(__file__).resolve().parents[2] / "demo_repo"

GOOD_FIX = json.dumps({"bug_location": "    return round(total * (1 + percent / 100), 2)",
                       "bug_type": "operator", "explanation": "adds instead of subtracting"}) + """
```python
def apply_discount(total, percent):
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return round(total * (1 - percent / 100), 2)
```"""
WRONG_FIX = GOOD_FIX.replace("(1 - percent / 100)", "(1 * percent / 100)")


class ScriptedModel:
    def __init__(self, *answers):
        self.answers, self.prompts = list(answers), []

    def __call__(self, messages):
        self.prompts.append(messages[-1]["content"])
        return self.answers.pop(0)


def test_target_of_a_test_is_the_repo_function_it_calls():
    assert target_of_test(DEMO, "tests/test_pricing.py::test_discount") == ("tinyshop/pricing.py", "apply_discount")


def test_replace_function_swaps_only_that_definition(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("import os\n\n\ndef a():\n    return 1\n\n\ndef b():\n    return 2\n")
    replace_function(f, "a", "def a():\n    return 10\n")
    assert f.read_text() == "import os\n\n\ndef a():\n    return 10\n\n\ndef b():\n    return 2\n"


def test_replace_function_rejects_code_without_that_function(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("def a():\n    return 1\n")
    with pytest.raises(ValueError):
        replace_function(f, "a", "def other():\n    return 1\n")
    assert f.read_text() == "def a():\n    return 1\n"


@needs_docker
def test_debug_fixes_the_failing_test_in_the_workspace_only():
    ws = open_workspace(DEMO)
    try:
        model = ScriptedModel(GOOD_FIX)
        fixes = debug_failing_tests(ws.path, model)
        assert [(f.test, f.fixed, f.attempts) for f in fixes] == [("tests/test_pricing.py::test_discount", True, 1)]
        assert "1 - percent / 100" in (ws.path / "tinyshop/pricing.py").read_text()
        assert "1 + percent / 100" in (DEMO / "tinyshop/pricing.py").read_text()
        assert "This test fails: `test_discount`" in model.prompts[0] and "55.0" in model.prompts[0]
    finally:
        ws.cleanup()


@needs_docker
def test_debug_retries_with_the_new_error_then_succeeds():
    ws = open_workspace(DEMO)
    try:
        model = ScriptedModel(WRONG_FIX, GOOD_FIX)
        fixes = debug_failing_tests(ws.path, model)
        assert fixes[0].fixed and fixes[0].attempts == 2
        assert "5.0 == 45.0" in model.prompts[1]
    finally:
        ws.cleanup()


@needs_docker
def test_debug_gives_up_after_three_attempts_and_restores_the_function():
    ws = open_workspace(DEMO)
    original = (ws.path / "tinyshop/pricing.py").read_text()
    try:
        fixes = debug_failing_tests(ws.path, ScriptedModel(WRONG_FIX, WRONG_FIX, WRONG_FIX))
        assert not fixes[0].fixed and fixes[0].attempts == 3
        assert (ws.path / "tinyshop/pricing.py").read_text() == original
    finally:
        ws.cleanup()
