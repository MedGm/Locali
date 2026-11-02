import shutil
import subprocess
import urllib.request

import pytest

from evaluation.tasks.codegen import (
    Problem,
    build_messages,
    evaluate_solution,
    load_humaneval_plus,
    load_mbpp_plus,
)

docker_ok = shutil.which("docker") is not None and subprocess.run(
    ["docker", "info"], capture_output=True, check=False
).returncode == 0
needs_docker = pytest.mark.skipif(not docker_ok, reason="Docker daemon not available")


def hub_reachable() -> bool:
    try:
        urllib.request.urlopen("https://huggingface.co", timeout=5)
        return True
    except OSError:
        return False


needs_hub = pytest.mark.skipif(not hub_reachable(), reason="Hugging Face Hub not reachable")

HUMANEVAL_STYLE = Problem(
    benchmark="humaneval_plus",
    task_id="toy/0",
    prompt='import math\n\n\ndef circle_area(r: float) -> float:\n    """Area of a circle."""\n',
    entry_point="circle_area",
    test="def check(candidate):\n    assert abs(candidate(1.0) - math.pi) < 1e-9\n",
    reference_solution="import math\n\n\ndef circle_area(r):\n    return math.pi * r * r\n",
)

MBPP_STYLE = Problem(
    benchmark="mbpp_plus",
    task_id="toy/1",
    prompt='"""\nWrite a function to double a number.\nassert double(2) == 4\n"""\n',
    entry_point="double",
    test="assert double(3) == 6\nassert double(0) == 0\n",
    reference_solution="def double(x):\n    return 2 * x\n",
)


def test_messages_use_evalplus_instruction_and_include_prompt():
    messages = build_messages(HUMANEVAL_STYLE)

    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"].startswith(
        "Please provide a self-contained Python script that solves the following problem"
    )
    assert "def circle_area(r: float)" in messages[-1]["content"]


@needs_docker
def test_correct_humaneval_style_solution_passes():
    # Solution omits `import math`; the prompt's imports must be supplied.
    outcome = evaluate_solution(HUMANEVAL_STYLE, "def circle_area(r):\n    return math.pi * r * r\n")
    assert outcome.passed, outcome.detail


@needs_docker
def test_wrong_solution_fails():
    outcome = evaluate_solution(HUMANEVAL_STYLE, "def circle_area(r):\n    return 2 * r\n")
    assert not outcome.passed
    assert outcome.status == "failed"


@needs_docker
def test_syntax_error_fails_cleanly():
    outcome = evaluate_solution(HUMANEVAL_STYLE, "def circle_area(r)\n    return r\n")
    assert not outcome.passed
    assert outcome.status == "failed"


@needs_docker
def test_infinite_loop_times_out():
    outcome = evaluate_solution(
        HUMANEVAL_STYLE, "def circle_area(r):\n    while True:\n        pass\n", timeout_s=8
    )
    assert not outcome.passed
    assert outcome.status == "timeout"


@needs_docker
def test_correct_mbpp_style_solution_passes():
    outcome = evaluate_solution(MBPP_STYLE, MBPP_STYLE.reference_solution)
    assert outcome.passed, outcome.detail


@needs_docker
@needs_hub
@pytest.mark.parametrize("loader", [load_humaneval_plus, load_mbpp_plus])
def test_reference_solutions_of_real_benchmarks_pass(loader):
    problems = loader(limit=3)

    assert len(problems) == 3
    for problem in problems:
        outcome = evaluate_solution(problem, problem.reference_solution)
        assert outcome.passed, (problem.task_id, outcome.detail)


@needs_hub
def test_loaders_skip_problems_that_fail_harness_validation():
    from evaluation.tasks.codegen import EXCLUDED

    he_ids = {p.task_id for p in load_humaneval_plus()}
    mbpp_ids = {p.task_id for p in load_mbpp_plus()}

    assert "HumanEval/32" in EXCLUDED and "Mbpp/255" in EXCLUDED
    assert not (he_ids | mbpp_ids) & set(EXCLUDED)
    assert (len(he_ids), len(mbpp_ids)) == (163, 377)


@needs_docker
def test_correct_solution_with_wrong_self_written_assert_passes():
    from evaluation.client import Completion
    from evaluation.tasks.codegen import HUMANEVAL_PLUS_TASK

    text = "```python\ndef circle_area(r):\n    return math.pi * r * r\n\n# Test cases\nassert circle_area(1) == 3\n```"
    scored = HUMANEVAL_PLUS_TASK.score(HUMANEVAL_STYLE, Completion(text, "", 1, 1, 0, 0, "stop"), 60)

    assert scored["passed"], scored
    assert "assert circle_area(1) == 3" in scored["raw_code"]


@needs_docker
def test_truncated_answer_with_complete_function_passes():
    from evaluation.client import Completion
    from evaluation.tasks.codegen import HUMANEVAL_PLUS_TASK

    text = "```python\ndef circle_area(r):\n    return math.pi * r * r\n\nassert circle_area(2) == math.pi * 4\nassert circle_are"
    scored = HUMANEVAL_PLUS_TASK.score(HUMANEVAL_STYLE, Completion(text, "", 1, 1, 0, 0, "length"), 60)

    assert scored["passed"], scored


def test_plan_variant_asks_for_a_plan_before_the_code():
    from evaluation.run import TASKS

    problem = Problem("humaneval_plus", "HumanEval/0", "def f(x):\n    \"\"\"Return x.\"\"\"\n", "f", "", "")
    plain = TASKS["humaneval_plus"].messages(problem)[0]["content"]
    plan = TASKS["humaneval_plus_plan"].messages(problem)[0]["content"]
    assert "def f(x):" in plan
    assert "plan" in plan.lower() and "plan" not in plain.lower()
    assert TASKS["humaneval_plus_plan"].excluded == TASKS["humaneval_plus"].excluded


def test_keepdoc_variant_asks_to_copy_the_docstring():
    from evaluation.run import TASKS

    problem = Problem("humaneval_plus", "HumanEval/0", "def f(x):\n    \"\"\"Return x.\"\"\"\n", "f", "", "")
    content = TASKS["humaneval_plus_keepdoc"].messages(problem)[0]["content"]
    assert "def f(x):" in content and "docstring" in content.lower()


HE_PROMPT = (
    "from typing import List\n\n\n"
    "def below(numbers: List[int], limit: int) -> bool:\n"
    "    \"\"\" Return True if every number is below limit.\n"
    "    >>> below([1, 2], 3)\n    True\n    \"\"\"\n"
)
MBPP_PROMPT = '"""\nWrite a function to add two numbers.\nassert add_two(1, 2) == 3\n"""\n'
MBPP_CODE = "def add_two(a, b):\n  return a + b\n"


def test_english_variant_states_the_signature_and_the_docstring_as_text():
    from evaluation.tasks.codegen import english_prompt

    text = english_prompt(Problem("humaneval_plus", "HumanEval/1", HE_PROMPT, "below", "", ""))

    assert "def " not in text
    assert "`below(numbers: List[int], limit: int) -> bool`" in text
    assert "Return True if every number is below limit." in text
    assert ">>> below([1, 2], 3)" in text
    assert text.startswith('"""\n') and text.endswith('"""\n')  # same shape as an MBPP+ prompt


def test_english_variant_keeps_helper_code_it_cannot_rephrase():
    from evaluation.tasks.codegen import english_prompt

    prompt = "def helper(s):\n    return s[::-1]\n\n\ndef main(s):\n    \"\"\"Undo helper.\"\"\"\n"
    text = english_prompt(Problem("humaneval_plus", "HumanEval/2", prompt, "main", "", ""))

    assert "def helper(s):" in text and "Undo helper." in text


def test_stub_variant_turns_an_mbpp_prompt_into_a_signature_with_docstring():
    from evaluation.tasks.codegen import stub_prompt

    text = stub_prompt(Problem("mbpp_plus", "Mbpp/1", MBPP_PROMPT, "add_two", "", MBPP_CODE))

    assert text.startswith("def add_two(a, b):\n    \"\"\"\n")
    assert "    Write a function to add two numbers.\n" in text
    assert "    assert add_two(1, 2) == 3\n" in text


def test_format_swap_tasks_use_the_standard_instruction_and_tests():
    from evaluation.run import TASKS
    from evaluation.tasks.codegen import INSTRUCTION

    he = Problem("humaneval_plus", "HumanEval/1", HE_PROMPT, "below", "", "")
    mb = Problem("mbpp_plus", "Mbpp/1", MBPP_PROMPT, "add_two", "", MBPP_CODE)
    english = TASKS["humaneval_plus_english"].messages(he)[0]["content"]
    stub = TASKS["mbpp_plus_stub"].messages(mb)[0]["content"]

    assert english.startswith(INSTRUCTION + "\n```\n") and "Return True if" in english
    assert stub.startswith(INSTRUCTION + "\n```\n") and "def add_two(a, b):" in stub
    assert TASKS["mbpp_plus_stub"].excluded == TASKS["mbpp_plus"].excluded
