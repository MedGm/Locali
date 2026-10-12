import json

from evaluation.client import Completion
from evaluation.tasks.internal import (
    InternalItem,
    InternalRepairTask,
    InternalReviewTask,
    InternalTestgenTask,
)
from evaluation.tasks.testgen import (
    testgen_prompt as make_testgen_prompt,  # name must not start with "test"
)
from evaluation.tests.test_codegen import needs_docker
from training.data.format import t1_messages
from training.data.tests.test_t1_bugs import CODE, SUITE

# a real fault (x >= hi would be equivalent for clamp: both return hi when x == hi)
BUGGY = CODE.replace("return hi\n", "return hi - 1\n")
EXAMPLE = {
    "bug_type": "off-by-one constant", "line": 5, "original_snippet": "hi", "mutated_snippet": "hi - 1",
    "buggy_code": BUGGY, "fixed_code": CODE,
    "failing_test": {"name": "TestClamp::test_edges", "code": "def test_edges(self): ...", "error": "AssertionError: 9 != 10"},
}
ITEM = InternalItem(task_id="t1-x-0", group="g1", messages=t1_messages(EXAMPLE, "The comparison treats hi as out of range."))
TASK = InternalRepairTask(rows=[], suites={"g1": SUITE})


def answer(text: str) -> Completion:
    return Completion(text, "", 10, 10, 0.1, 0.2, "stop")


def test_prompt_is_the_training_prompt_without_the_answer():
    assert TASK.messages(ITEM) == ITEM.messages[:-1]


@needs_docker
def test_reference_answer_passes_with_exact_fix_and_correct_location():
    scored = TASK.score(ITEM, answer(TASK.reference(ITEM)), 60)
    assert (scored["passed"], scored["exact_fix"], scored["location_correct"], scored["format_valid"]) == (True, True, True, True)


@needs_docker
def test_unfixed_code_fails_the_suite():
    text = json.dumps({"bug_location": "        return hi - 1", "bug_type": "x", "explanation": "y"}) + f"\n```python\n{BUGGY}```"
    scored = TASK.score(ITEM, answer(text), 60)
    assert scored["passed"] is False and scored["exact_fix"] is False and scored["location_correct"] is True


@needs_docker
def test_reformatted_fix_counts_as_exact_and_plain_code_is_format_invalid():
    reformatted = CODE.replace("    return x\n", "    return (x)  # unchanged\n")
    scored = TASK.score(ITEM, answer(f"```python\n{reformatted}```"), 60)
    assert scored["passed"] and scored["exact_fix"]
    assert scored["format_valid"] is False and scored["location_correct"] is False


def test_metrics():
    records = [{"passed": True, "exact_fix": True, "location_correct": True, "format_valid": True},
               {"passed": False, "exact_fix": False, "location_correct": True, "format_valid": True}]
    assert TASK.metrics(records) == {"pass@1": 0.5, "exact_fix_rate": 0.5, "location_accuracy": 1.0, "format_valid_rate": 1.0}


# ---- internal_t3 (review) ----


REVIEW = InternalReviewTask(rows=[])


def review_item(task_id, findings):
    return InternalItem(task_id=task_id, group="g", messages=[
        {"role": "user", "content": "Review ..."},
        {"role": "assistant", "content": json.dumps({"findings": findings})},
    ])


BUG = {"line": "    return x >= 0", "category": "bug", "severity": "high", "message": "m"}
QUALITY = {"line": "import os", "category": "quality", "severity": "low", "message": "unused"}


def review(findings):
    return answer(json.dumps({"findings": findings}))


def test_buggy_item_needs_a_bug_finding_on_the_right_line():
    item = review_item("t3-t1-1-0-buggy", [BUG])
    assert REVIEW.score(item, review([{**BUG, "line": "return x >= 0  "}]), 1)["correct"] is True
    assert REVIEW.score(item, review([{**BUG, "line": "def pos(x):"}]), 1)["correct"] is False
    assert REVIEW.score(item, review([]), 1)["correct"] is False


def test_clean_item_must_not_report_a_bug():
    item = review_item("t3-t1-1-0-clean", [])
    assert REVIEW.score(item, review([]), 1)["correct"] is True
    assert REVIEW.score(item, review([QUALITY]), 1)["correct"] is True
    assert REVIEW.score(item, review([BUG]), 1)["correct"] is False


def test_tool_item_scores_line_recall_and_unparseable_answers_are_invalid():
    item = review_item("t3-self-oss-7", [QUALITY])
    scored = REVIEW.score(item, review([QUALITY]), 1)
    assert scored["kind"] == "tool" and scored["line_recall"] == 1.0 and scored["correct"]
    bad = REVIEW.score(item, answer("looks fine"), 1)
    assert bad["format_valid"] is False and bad["correct"] is False


def test_review_metrics():
    records = [
        {"kind": "buggy", "correct": True, "format_valid": True, "line_recall": None},
        {"kind": "buggy", "correct": False, "format_valid": True, "line_recall": None},
        {"kind": "clean", "correct": True, "format_valid": True, "line_recall": None},
        {"kind": "tool", "correct": False, "format_valid": False, "line_recall": 0.5},
    ]
    m = REVIEW.metrics(records)
    assert m["bug_recall"] == 0.5 and m["clean_specificity"] == 1.0
    assert m["pair_accuracy"] == round(2 / 3, 4) and m["tool_line_recall"] == 0.5 and m["format_valid_rate"] == 0.75


# ---- internal_t2 (tests) ----


T2_ITEM = InternalItem(task_id="t2-1", group="KAKA22/CodeRM-UnitTest:1", messages=[
    {"role": "user", "content": make_testgen_prompt("clamp", CODE)},
    {"role": "assistant", "content": "```python\nfrom solution import clamp\n\ndef test_low():\n    assert clamp(-1, 0, 10) == 0\n\n"
                                     "def test_high():\n    assert clamp(11, 0, 10) == 10\n\ndef test_in():\n    assert clamp(5, 0, 10) == 5\n```"},
])


@needs_docker
def test_t2_reference_tests_are_valid_and_kill_mutants():
    task = InternalTestgenTask(rows=[])
    scored = task.score(T2_ITEM, answer(task.reference(T2_ITEM)), 60)
    assert scored["tests_passed_on_correct"] == 3 and scored["mutants_tried"] >= 1 and scored["mutants_killed"] >= 1


@needs_docker
def test_t2_tests_failing_on_correct_code_kill_nothing():
    task = InternalTestgenTask(rows=[])
    wrong = "```python\nfrom solution import clamp\n\ndef test_wrong():\n    assert clamp(5, 0, 10) == 6\n```"
    scored = task.score(T2_ITEM, answer(wrong), 60)
    assert scored["tests_passed_on_correct"] == 0 and scored["mutants_killed"] == 0
