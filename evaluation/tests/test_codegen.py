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
