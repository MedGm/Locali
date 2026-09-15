from dataclasses import replace

import pytest

from evaluation.client import Completion
from evaluation.tasks.refactor import REFACTOR_TASK, quality_metrics
from evaluation.tests.test_codegen import HUMANEVAL_STYLE, needs_docker

BRANCHY = """
import math


def classify(x):
    if x < 0:
        return "negative"
    elif x == 0:
        return "zero"
    return "positive"
"""


def answer(text: str) -> Completion:
    return Completion(text, "", 10, 10, 0.1, 0.2, "stop")


def test_quality_metrics_measure_complexity_lint_and_size():
    q = quality_metrics(BRANCHY)

    assert q["cyclomatic_complexity"] == 3
    assert q["ruff_violations"] == 1  # unused `import math`
    assert q["sloc"] == 7
    assert 0 < q["maintainability_index"] <= 100


def test_quality_metrics_return_none_for_unparseable_code():
    assert quality_metrics("def broken(:\n    pass") is None


def test_prompt_asks_to_keep_behaviour_and_signature():
    content = REFACTOR_TASK.messages(HUMANEVAL_STYLE)[-1]["content"]

    assert "without changing its behaviour" in content
    assert "same function name and signature" in content
    assert "def circle_area(r):" in content


@needs_docker
def test_unchanged_code_preserves_behaviour_with_zero_deltas():
    scored = REFACTOR_TASK.score(HUMANEVAL_STYLE, answer(REFACTOR_TASK.reference(HUMANEVAL_STYLE)), 60)

    assert scored["behaviour_preserved"] is True
    assert scored["delta_cyclomatic_complexity"] == 0
    assert scored["delta_ruff_violations"] == 0
    assert scored["status"] == "preserved_not_improved"


@needs_docker
def test_changed_behaviour_is_detected():
    broken = "```python\ndef circle_area(r):\n    return r * r\n```"

    scored = REFACTOR_TASK.score(HUMANEVAL_STYLE, answer(broken), 60)

    assert scored["behaviour_preserved"] is False
    assert scored["status"] == "behaviour_changed"


@needs_docker
def test_removing_a_lint_violation_counts_as_improvement():
    messy = replace(HUMANEVAL_STYLE, reference_solution="import math\nimport os\n\n\ndef circle_area(r):\n    return math.pi * r * r\n")
    clean = "```python\nimport math\n\n\ndef circle_area(r):\n    return math.pi * r * r\n```"

    scored = REFACTOR_TASK.score(messy, answer(clean), 60)

    assert scored["delta_ruff_violations"] == -1
    assert scored["status"] == "preserved_improved"


def test_metrics_report_preservation_and_mean_deltas():
    records = [
        {"status": "preserved_improved", "behaviour_preserved": True, "delta_cyclomatic_complexity": -2,
         "delta_maintainability_index": 5.0, "delta_ruff_violations": -1},
        {"status": "preserved_not_improved", "behaviour_preserved": True, "delta_cyclomatic_complexity": 0,
         "delta_maintainability_index": -1.0, "delta_ruff_violations": 0},
        {"status": "behaviour_changed", "behaviour_preserved": False, "delta_cyclomatic_complexity": -5,
         "delta_maintainability_index": 20.0, "delta_ruff_violations": -3},
    ]

    m = REFACTOR_TASK.metrics(records)

    assert m["behaviour_preserved_rate"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["improved_rate"] == pytest.approx(1 / 3, abs=1e-4)
    # deltas averaged over behaviour-preserving refactorings only
    assert m["mean_delta_cyclomatic_complexity"] == -1.0
    assert m["mean_delta_maintainability_index"] == 2.0
    assert m["mean_delta_ruff_violations"] == -0.5
