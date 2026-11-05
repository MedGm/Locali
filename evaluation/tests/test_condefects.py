
import pytest

from evaluation.client import Completion
from evaluation.tasks.condefects import (
    ConDefectsTask,
    DefectItem,
    case_folder,
    harness_check,
    run_cases,
)
from evaluation.tests.test_codegen import needs_docker

CORRECT = "a, b = map(int, input().split())\nprint(a + b)\n"
FAULTY = "a, b = map(int, input().split())\nprint(a - b)\n"


@pytest.fixture
def tests(tmp_path):
    root = tmp_path / "Test" / "abc999" / "A"
    for name, given, want in [("01.txt", "1 1", "2"), ("02_big.txt", "10 3", "13"), ("00_zero.txt", "0 0", "0")]:
        for kind, text in (("in", given), ("out", want)):
            (root / kind).mkdir(parents=True, exist_ok=True)
            (root / kind / name).write_text(text + "\n")
    return root


def test_tests_dir_maps_task_to_upper_letter(tests):
    assert case_folder(tests.parents[1], "abc999_a") == tests
    assert case_folder(tests.parents[1], "abc999_b") is None


@needs_docker
def test_run_cases_stops_at_the_smallest_failing_input(tests):
    assert run_cases(CORRECT, tests).passed == 3
    run = run_cases(FAULTY, tests)
    # smallest input first, stop at the first failure
    assert run.failed_cases == ["01.txt"]
    assert run.results["01.txt"] == "0\n"


@needs_docker
def test_harness_check_shows_the_smallest_failing_input_and_scores_answers(tests, monkeypatch):
    monkeypatch.setenv("CONDEFECTS_TESTS", str(tests.parents[1]))
    item = DefectItem("abc999_a/1", "2024-03-01", FAULTY, CORRECT, "abc999/A")
    assert harness_check(item, tests.parents[1]) == (True, "kept")
    assert (item.shown_input, item.shown_expected, item.shown_actual) == ("1 1", "2", "0")
    task = ConDefectsTask()
    prompt = task.messages(item)[0]["content"]
    assert "print(a - b)" in prompt and "Input:\n1 1\nExpected output:\n2\nActual output:\n0" in prompt
    answer = Completion(f"```python\n{CORRECT}```", "", 1, 1, 0, 0, "stop")
    assert task.score(item, answer, 60)["passed"]
    assert not task.score(item, Completion("```python\nwhile True: pass\n```", "", 1, 1, 0, 0, "stop"), 60)["passed"]


@needs_docker
def test_harness_check_drops_a_faulty_version_that_passes(tests):
    assert harness_check(DefectItem("abc999_a/2", "2024-03-01", CORRECT, CORRECT, "abc999/A"), tests.parents[1])[0] is False
