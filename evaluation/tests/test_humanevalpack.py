import pytest

from evaluation.client import Completion
from evaluation.tasks.humanevalpack import BUG_DETECT_TASK, FIX_TASK, parse_has_bug
from evaluation.tests.test_codegen import needs_docker, needs_hub


def answer(text: str) -> Completion:
    return Completion(text, "", 10, 10, 0.1, 0.2, "stop")


# ---- parsing the detection verdict ----

@pytest.mark.parametrize(("text", "expected"), [
    ('{"has_bug": true, "reason": "off by one"}', True),
    ('```json\n{"has_bug": false, "reason": "correct"}\n```', False),
    ('Looking at it...\n{"has_bug": true}\nDone.', True),
    ('<think>{"has_bug": false}</think>{"has_bug": true}', True),
    ("has_bug: False", False),
    ("I think the code is fine.", None),
])
def test_parse_has_bug(text, expected):
    assert parse_has_bug(text) is expected


# ---- bug detection metrics ----

def records(pairs):
    """pairs of (label, predicted) -> records as the task would score them."""
    return [{"label": label, "predicted": pred} for label, pred in pairs]


def test_detection_metrics_precision_recall_f1():
    # TP=2, FN=1, FP=1, TN=1
    m = BUG_DETECT_TASK.metrics(records([(True, True), (True, True), (True, False), (False, True), (False, False)]))

    assert m["precision"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["recall"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["f1"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["accuracy"] == pytest.approx(3 / 5, abs=1e-4)


def test_detection_counts_unparseable_answers_as_invalid_and_not_as_bug_reports():
    m = BUG_DETECT_TASK.metrics(records([(True, None), (False, None), (True, True)]))

    assert m["invalid_rate"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["recall"] == pytest.approx(1 / 2, abs=1e-4)
    assert m["precision"] == pytest.approx(1.0, abs=1e-4)
    assert m["accuracy"] == pytest.approx(1 / 3, abs=1e-4)


# ---- loading and prompts (real dataset) ----

@needs_hub
def test_detection_items_pair_buggy_and_correct_versions():
    items = BUG_DETECT_TASK.load(limit=2)

    assert [i.task_id for i in items] == ["Python/0/buggy", "Python/0/correct", "Python/1/buggy", "Python/1/correct"]
    assert [i.label for i in items] == [True, False, True, False]
    assert "distance = elem - elem2" in BUG_DETECT_TASK.messages(items[0])[-1]["content"]
    assert "Check if in given list of numbers" in BUG_DETECT_TASK.messages(items[1])[-1]["content"]


@needs_hub
def test_detection_scores_a_correct_verdict():
    buggy = BUG_DETECT_TASK.load(limit=1)[0]

    scored = BUG_DETECT_TASK.score(buggy, answer('{"has_bug": true}'), eval_timeout_s=1)

    assert scored["status"] == "correct"
    assert scored["predicted"] is True


@needs_hub
def test_fix_prompt_shows_buggy_code_and_tests():
    item = FIX_TASK.load(limit=1)[0]
    content = FIX_TASK.messages(item)[-1]["content"]

    assert content.startswith("Fix bugs in has_close_elements.")
    assert "distance = elem - elem2" in content
    assert "def check(has_close_elements)" in content


@needs_docker
@needs_hub
def test_fix_reference_passes_and_buggy_code_fails():
    for item in FIX_TASK.load(limit=3):
        fixed = FIX_TASK.score(item, answer(FIX_TASK.reference(item)), eval_timeout_s=60)
        unfixed = FIX_TASK.score(item, answer(f"```python\n{item.declaration}{item.buggy_solution}\n```"), 60)

        assert fixed["passed"], (item.task_id, fixed)
        assert not unfixed["passed"], item.task_id
