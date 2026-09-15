from dataclasses import replace

from evaluation.client import Completion
from evaluation.tasks.completion import COMPLETION_TASK, make_infill, reindent
from evaluation.tests.test_codegen import HUMANEVAL_STYLE, needs_docker

FIVE_LINE = replace(
    HUMANEVAL_STYLE,
    reference_solution=(
        "import math\n\n\ndef circle_area(r):\n"
        "    if r < 0:\n"
        "        raise ValueError('negative')\n"
        "    squared = r * r\n"
        "    area = math.pi * squared\n"
        "    return area\n"
    ),
)


def answer(text: str) -> Completion:
    return Completion(text, "", 10, 10, 0.1, 0.2, "stop")


def test_infill_masks_a_middle_span_of_the_body_deterministically():
    infill = make_infill(FIVE_LINE)

    assert infill.prefix + infill.middle + infill.suffix == FIVE_LINE.reference_solution
    assert infill.middle == "        raise ValueError('negative')\n    squared = r * r\n    area = math.pi * squared\n"
    assert make_infill(FIVE_LINE) == infill


def test_prompt_hides_the_masked_code():
    content = COMPLETION_TASK.messages(FIVE_LINE)[-1]["content"]

    assert "<FILL_ME>" in content
    assert "squared = r * r" not in content
    assert "return area" in content


def test_reindent_aligns_dedented_block_to_masked_indentation():
    block = "raise ValueError('negative')\nsquared = r * r"
    assert reindent(block, "        ") == "        raise ValueError('negative')\n        squared = r * r"


def test_reindent_keeps_relative_indentation():
    block = "if x:\n    y = 1"
    assert reindent(block, "    ") == "    if x:\n        y = 1"


@needs_docker
def test_reference_fill_passes():
    scored = COMPLETION_TASK.score(FIVE_LINE, answer(COMPLETION_TASK.reference(FIVE_LINE)), 60)
    assert scored["passed"], scored
    assert scored["returned_full_function"] is False


@needs_docker
def test_wrong_fill_fails():
    wrong = "```python\n        raise ValueError('negative')\n    squared = r + 1\n    area = math.pi * squared\n```"
    assert not COMPLETION_TASK.score(FIVE_LINE, answer(wrong), 60)["passed"]


@needs_docker
def test_full_function_answer_is_scored_and_flagged():
    full = "```python\ndef circle_area(r):\n    return math.pi * r * r\n```"

    scored = COMPLETION_TASK.score(FIVE_LINE, answer(full), 60)

    assert scored["passed"]
    assert scored["returned_full_function"] is True


def test_metrics_report_pass_rate_and_full_function_rate():
    records = [{"passed": True, "returned_full_function": False}, {"passed": False, "returned_full_function": True}]
    m = COMPLETION_TASK.metrics(records)
    assert (m["pass@1"], m["full_function_rate"]) == (0.5, 0.5)
