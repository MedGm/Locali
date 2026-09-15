import pytest

from evaluation.client import Completion
from evaluation.tasks.testgen import TESTGEN_TASK
from evaluation.tests.test_codegen import needs_docker, needs_hub


def answer(text: str) -> Completion:
    return Completion(text, "", 10, 10, 0.1, 0.2, "stop")


@pytest.fixture(scope="module")
def item():
    return TESTGEN_TASK.load(limit=1)[0]  # Python/0 has_close_elements; buggy version drops abs()


@needs_hub
def test_prompt_shows_specified_function_and_import_path(item):
    content = TESTGEN_TASK.messages(item)[-1]["content"]

    assert "from solution import has_close_elements" in content
    assert "Check if in given list of numbers" in content
    assert "distance = abs(elem - elem2)" in content


@needs_docker
@needs_hub
def test_reference_tests_are_valid_and_catch_the_bug(item):
    scored = TESTGEN_TASK.score(item, answer(TESTGEN_TASK.reference(item)), eval_timeout_s=60)

    assert scored["status"] == "valid_caught_bug", scored
    assert 0 < scored["coverage_percent"] <= 100


@needs_docker
@needs_hub
def test_weak_tests_are_valid_but_miss_the_bug(item):
    weak = "```python\nfrom solution import has_close_elements\n\ndef test_exists():\n    assert callable(has_close_elements)\n```"

    scored = TESTGEN_TASK.score(item, answer(weak), eval_timeout_s=60)

    assert scored["status"] == "valid_missed_bug", scored


@needs_docker
@needs_hub
def test_tests_failing_on_correct_code_are_invalid(item):
    wrong = "```python\nfrom solution import has_close_elements\n\ndef test_wrong():\n    assert has_close_elements([1.0, 2.0], 0.5) is True\n```"

    scored = TESTGEN_TASK.score(item, answer(wrong), eval_timeout_s=60)

    assert scored["status"] == "invalid_tests", scored
    assert scored["caught_bug"] is False


@needs_docker
@needs_hub
def test_answer_without_tests_is_invalid(item):
    scored = TESTGEN_TASK.score(item, answer("I cannot write tests for this."), eval_timeout_s=60)

    assert scored["status"] == "invalid_tests"


def test_metrics_separate_validity_bug_detection_and_coverage():
    records = [
        {"status": "valid_caught_bug", "valid": True, "caught_bug": True, "coverage_percent": 100.0, "tests_collected": 4},
        {"status": "valid_missed_bug", "valid": True, "caught_bug": False, "coverage_percent": 50.0, "tests_collected": 2},
        {"status": "invalid_tests", "valid": False, "caught_bug": False, "coverage_percent": None, "tests_collected": 0},
        {"status": "invalid_tests", "valid": False, "caught_bug": False, "coverage_percent": 90.0, "tests_collected": 3},
    ]

    m = TESTGEN_TASK.metrics(records)

    assert m["valid_rate"] == 0.5
    assert m["bug_detection_rate"] == 0.25
    assert m["bug_detection_rate_among_valid"] == 0.5
    assert m["mean_coverage_valid"] == 75.0
