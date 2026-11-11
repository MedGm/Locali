import json
from pathlib import Path

import pytest

from backend.agents.debug import debug_failing_tests, replace_function, target_of_test
from backend.agents.model import guarded
from backend.workspace import open_workspace
from evaluation.tests.test_codegen import needs_docker
from training.data.format import fix_prompt, parse_explanation

DEMO = Path(__file__).resolve().parents[2] / "demo_repo"

DIAGNOSIS = json.dumps({"bug_type": "operator", "explanation": "adds instead of subtracting"})
GOOD_FIX = """```python
def apply_discount(total, percent):
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return round(total * (1 - percent / 100), 2)
```"""
WRONG_FIX = GOOD_FIX.replace("(1 - percent / 100)", "(1 * percent / 100)")


class ScriptedModel:
    def __init__(self, *answers):
        self.answers, self.prompts, self.temperatures = list(answers), [], []

    def __call__(self, messages, temperature=0.0):
        self.prompts.append(messages[-1]["content"])
        self.temperatures.append(temperature)
        return self.answers.pop(0)


def test_fix_prompt_asks_for_code_only_and_adds_the_error_on_a_retry():
    first = fix_prompt("f", "def f():\n    return 1\n", "def test_f():\n    assert f() == 2\n")
    assert first.startswith("Fix bugs in f.") and "These tests fail:" in first and "bug_location" not in first
    assert "Running the tests gives" not in first
    assert "Running the tests gives:\n```\nassert 1 == 2\n```" in fix_prompt("f", "x", "y", "assert 1 == 2")


def test_explanation_is_read_from_json_and_other_answers_give_none():
    assert parse_explanation('Sure: {"bug_type": "operator", "explanation": "adds {x}"} done') == {
        "bug_type": "operator", "explanation": "adds {x}"}
    assert parse_explanation("it added instead of subtracting") is None


def test_guard_passes_a_temperature_only_to_models_that_take_one():
    calls, plain, sampled = [], lambda messages: "a", ScriptedModel("b")
    assert guarded(plain, calls.append, lambda: "debug")([{"role": "user", "content": "x"}], temperature=0.6) == "a"
    assert guarded(sampled, calls.append, lambda: "debug")([{"role": "user", "content": "x"}], temperature=0.6) == "b"
    assert sampled.temperatures == [0.6] and ["temperature" in c for c in calls] == [False, True]


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
        model = ScriptedModel(GOOD_FIX, DIAGNOSIS)
        fixes = debug_failing_tests(ws.path, model)
        assert [(f.test, f.fixed, f.attempts) for f in fixes] == [("tests/test_pricing.py::test_discount", True, 1)]
        assert "1 - percent / 100" in (ws.path / "tinyshop/pricing.py").read_text()
        assert "1 + percent / 100" in (DEMO / "tinyshop/pricing.py").read_text()
        assert model.prompts[0].startswith("Fix bugs in apply_discount.") and "def test_discount" in model.prompts[0]
        # the explanation is asked once the fix passes; the bug's line comes from the diff, not from the model
        assert "1 + percent / 100" in model.prompts[1] and "1 - percent / 100" in model.prompts[1]
        assert fixes[0].diagnosis == {"bug_location": "    return round(total * (1 + percent / 100), 2)",
                                      "bug_type": "operator", "explanation": "adds instead of subtracting"}
    finally:
        ws.cleanup()


@needs_docker
def test_debug_retries_with_the_new_error_then_succeeds():
    ws = open_workspace(DEMO)
    try:
        model = ScriptedModel(WRONG_FIX, GOOD_FIX, "no json here")
        fixes = debug_failing_tests(ws.path, model)
        assert fixes[0].fixed and fixes[0].attempts == 2 and fixes[0].diagnosis is None
        assert "Running the tests gives" not in model.prompts[0]
        assert "5.0 == 45.0" in model.prompts[1] and "1 * percent / 100" in model.prompts[1]
        assert model.temperatures == [0.0, 0.6, 0.0]  # only the retry is sampled
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
