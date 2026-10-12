import pytest

from evaluation.client import Completion
from evaluation.tasks.testgen import TESTGEN_TASK
from evaluation.tests.test_codegen import needs_docker, needs_hub

HEADER = "```python\nfrom solution import has_close_elements\n\n"
# Python/0: the buggy version drops abs(), so [1.0, 2.0] at threshold 0.5 becomes "close".
CATCHES_BUG = "def test_far():\n    assert has_close_elements([1.0, 2.0], 0.5) is False\n"
WRONG_ORACLE = "def test_wrong():\n    assert has_close_elements([1.0, 2.0], 0.5) is True\n"
WEAK = "def test_exists():\n    assert callable(has_close_elements)\n"


def answer(text: str, finish: str = "stop") -> Completion:
    return Completion(text, "", 10, 10, 0.1, 0.2, finish)


@pytest.fixture(scope="module")
def item():
    return TESTGEN_TASK.load(limit=1)[0]


@needs_hub
def test_prompt_shows_specified_function_and_import_path(item):
    content = TESTGEN_TASK.messages(item)[-1]["content"]

    assert "from solution import has_close_elements" in content
    assert "Check if in given list of numbers" in content
    assert "distance = abs(elem - elem2)" in content


@needs_docker
@needs_hub
def test_reference_tests_are_strictly_valid_and_catch_the_bug(item):
    scored = TESTGEN_TASK.score(item, answer(TESTGEN_TASK.reference(item)), eval_timeout_s=60)

    assert scored["status"] == "caught_bug", scored
    assert scored["strict_valid"] is True
    assert 0 < scored["coverage_percent"] <= 100


@needs_docker
@needs_hub
def test_weak_tests_miss_the_bug(item):
    scored = TESTGEN_TASK.score(item, answer(HEADER + WEAK + "```"), eval_timeout_s=60)

    assert scored["status"] == "missed_bug", scored


@needs_docker
@needs_hub
def test_wrong_tests_are_discarded_and_the_rest_still_counts(item):
    scored = TESTGEN_TASK.score(item, answer(HEADER + WRONG_ORACLE + "\n" + CATCHES_BUG + "```"), eval_timeout_s=60)

    assert scored["status"] == "caught_bug", scored
    assert scored["strict_valid"] is False
    assert (scored["tests_collected"], scored["tests_passed_on_correct"]) == (2, 1)


@needs_docker
@needs_hub
def test_only_wrong_tests_means_no_valid_tests(item):
    scored = TESTGEN_TASK.score(item, answer(HEADER + WRONG_ORACLE + "```"), eval_timeout_s=60)

    assert scored["status"] == "no_valid_tests", scored
    assert scored["caught_bug"] is False
    assert scored["coverage_percent"] is None


@needs_docker
@needs_hub
def test_answer_without_tests_has_no_valid_tests(item):
    scored = TESTGEN_TASK.score(item, answer("I cannot write tests for this."), eval_timeout_s=60)

    assert scored["status"] == "no_valid_tests"


@needs_docker
@needs_hub
def test_tests_split_over_several_blocks_are_joined_and_flagged(item):
    text = (
        "Import first:\n```python\nfrom solution import has_close_elements\n```\n"
        f"Then a test:\n```python\n{CATCHES_BUG}```"
    )

    scored = TESTGEN_TASK.score(item, answer(text), eval_timeout_s=60)

    assert scored["status"] == "caught_bug", scored
    assert scored["multi_block"] is True


@needs_docker
@needs_hub
def test_truncated_test_file_keeps_complete_tests(item):
    text = HEADER + CATCHES_BUG + "\ndef test_more():\n    assert has_close_elements([1.0, 2.0"

    scored = TESTGEN_TASK.score(item, answer(text, finish="length"), eval_timeout_s=60)

    assert scored["status"] == "caught_bug", scored
    assert scored["trimmed"] is True


def test_metrics_report_validity_detection_and_coverage():
    records = [
        {"status": "caught_bug", "strict_valid": True, "caught_bug": True, "tests_collected": 4,
         "tests_passed_on_correct": 4, "coverage_percent": 100.0, "multi_block": False},
        {"status": "missed_bug", "strict_valid": False, "caught_bug": False, "tests_collected": 4,
         "tests_passed_on_correct": 2, "coverage_percent": 50.0, "multi_block": True},
        {"status": "no_valid_tests", "strict_valid": False, "caught_bug": False, "tests_collected": 2,
         "tests_passed_on_correct": 0, "coverage_percent": None, "multi_block": False},
        {"status": "no_valid_tests", "strict_valid": False, "caught_bug": False, "tests_collected": 0,
         "tests_passed_on_correct": 0, "coverage_percent": None, "multi_block": False},
    ]

    m = TESTGEN_TASK.metrics(records)

    assert m["strict_valid_rate"] == 0.25
    assert m["test_pass_rate"] == 0.6  # 6 of 10 generated tests pass on the correct code
    assert m["any_valid_test_rate"] == 0.5
    assert m["bug_detection_rate"] == 0.25
    assert m["mean_coverage_valid"] == 75.0
    assert m["mean_coverage_all"] == 37.5  # items without valid tests count as 0 %
    assert m["multi_block_rate"] == 0.25
