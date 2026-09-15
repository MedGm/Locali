import pytest

from evaluation.client import Completion
from evaluation.tasks.cruxeval import CRUX_OUTPUT_TASK, CruxItem, parse_prediction
from evaluation.tests.test_codegen import needs_docker, needs_hub

ITEM = CruxItem(task_id="toy_0", code="def f(s):\n    return s + 'a'", input='"x9j"', output="'x9ja'")


def answer(text: str) -> Completion:
    return Completion(text, "", 10, 10, 0.1, 0.2, "stop")


@pytest.mark.parametrize(("text", "expected"), [
    ('assert f("x9j") == "x9ja"\n[/ANSWER]', '"x9ja"'),
    ('[ANSWER]\nassert f(1) == [1, 2]\n[/ANSWER]', "[1, 2]"),
    ('```python\nassert f(1) == {"a": 1}\n```', '{"a": 1}'),
    ("<think>assert f(1) == 5</think>assert f(1) == 6", "6"),
])
def test_parse_prediction(text, expected):
    assert parse_prediction(text) == expected


def test_prompt_uses_official_format_with_the_item():
    content = CRUX_OUTPUT_TASK.messages(ITEM)[-1]["content"]

    assert content.startswith("You are given a Python function and an assertion containing an input")
    assert "def f(s):\n    return s + 'a'" in content
    assert content.rstrip().endswith('assert f("x9j") == ??\n[/PYTHON]\n[ANSWER]')


@needs_docker
def test_correct_prediction_passes():
    assert CRUX_OUTPUT_TASK.score(ITEM, answer('assert f("x9j") == "x9ja"'), eval_timeout_s=30)["passed"]


@needs_docker
def test_wrong_prediction_fails():
    scored = CRUX_OUTPUT_TASK.score(ITEM, answer('assert f("x9j") == "x9j"'), eval_timeout_s=30)
    assert scored["status"] == "failed"


def test_prediction_that_calls_the_function_is_rejected_without_execution():
    scored = CRUX_OUTPUT_TASK.score(ITEM, answer('assert f("x9j") == f("x9j")'), eval_timeout_s=30)
    assert scored["status"] == "invalid"
    assert not scored["passed"]


@needs_hub
def test_loads_all_800_problems():
    items = CRUX_OUTPUT_TASK.load()
    assert len(items) == 800
    assert items[0].task_id == "sample_0"
