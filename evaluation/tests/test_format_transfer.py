import json

from evaluation.client import Completion
from evaluation.tasks.format_transfer import ReviewFormatDetectTask, T1FormatFixTask
from evaluation.tasks.humanevalpack import PackItem
from evaluation.tests.test_codegen import needs_docker

ITEM = PackItem(
    task_id="Python/x", prompt="def add(a, b):\n    \"\"\"Add.\"\"\"\n", declaration="def add(a, b):\n",
    canonical_solution="    return a + b\n", buggy_solution="    return a - b\n", bug_type="operator misuse",
    entry_point="add", imports="", test_setup="",
    test="def check(add):\n    assert add(1, 2) == 3\n\ncheck(add)\n",
)
ERRORS = {"Python/x": "AssertionError"}


def answer(text: str) -> Completion:
    return Completion(text, "", 1, 1, 0.1, 0.2, "stop")


def test_t1_format_prompt_shows_buggy_code_test_and_recorded_error():
    task = T1FormatFixTask(errors=ERRORS)
    content = task.messages(ITEM)[-1]["content"]
    assert content.startswith("The following Python function has a bug.")
    assert "return a - b" in content and "def check(add):" in content and "AssertionError" in content
    assert '"bug_location"' in content


@needs_docker
def test_t1_format_scores_the_fixed_code_from_a_t1_answer():
    task = T1FormatFixTask(errors=ERRORS)
    good = json.dumps({"bug_location": "    return a - b", "bug_type": "t", "explanation": "e"}) + "\n```python\ndef add(a, b):\n    return a + b\n```"
    bad = json.dumps({"bug_location": "x", "bug_type": "t", "explanation": "e"}) + "\n```python\ndef add(a, b):\n    return a - b\n```"
    assert task.score(ITEM, answer(good), 60)["passed"]
    assert not task.score(ITEM, answer(bad), 60)["passed"]


def test_review_format_detection_counts_bug_findings():
    task = ReviewFormatDetectTask(items=[])
    buggy = task._items_from([ITEM])[0]
    clean = task._items_from([ITEM])[1]
    found = answer(json.dumps({"findings": [{"line": "    return a - b", "category": "bug", "severity": "high", "message": "m"}]}))
    quality_only = answer(json.dumps({"findings": [{"line": "x", "category": "quality", "severity": "low", "message": "m"}]}))
    assert "Review the following Python code" in task.messages(buggy)[-1]["content"]
    assert task.score(buggy, found, 1)["status"] == "correct"
    assert task.score(clean, quality_only, 1)["status"] == "correct"
    assert task.score(clean, found, 1)["status"] == "incorrect"
    assert task.score(buggy, answer("nothing parseable"), 1)["status"] == "invalid"
