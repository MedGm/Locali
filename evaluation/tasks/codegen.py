"""Code-generation benchmarks: EvalPlus HumanEval+ and MBPP+.

Prompts follow EvalPlus' instruction format for chat models so scores are comparable with
published EvalPlus numbers (without its assistant-prefill line, which chat APIs do not support).
Solutions run inside the Docker sandbox, never on the host.
"""

import ast
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from security.sandbox import run_pytest

HUMANEVAL_PLUS = ("evalplus/humanevalplus", "d32357cf319e50e9c8d8dab5ea876c72b0fd321b")
MBPP_PLUS = ("evalplus/mbppplus", "b2d74c91837c3f2a20c1299ae98133cbe7cfa077")

INSTRUCTION = (
    "Please provide a self-contained Python script that solves the following problem "
    "in a markdown code block:"
)


@dataclass
class Problem:
    benchmark: str
    task_id: str
    prompt: str
    entry_point: str
    test: str
    reference_solution: str


@dataclass
class Outcome:
    passed: bool
    status: str  # passed | failed | timeout | crashed
    detail: str
    duration_s: float


def build_messages(problem: Problem) -> list[dict]:
    return [{"role": "user", "content": f"{INSTRUCTION}\n```\n{problem.prompt.strip()}\n```\n"}]


def _prompt_imports(prompt: str) -> str:
    return "\n".join(
        line for line in prompt.splitlines() if line.startswith(("import ", "from "))
    )


def build_program(problem: Problem, code: str) -> str:
    if problem.benchmark == "humaneval_plus":
        return f"{_prompt_imports(problem.prompt)}\n\n{code}\n\n{problem.test}\n\ncheck({problem.entry_point})\n"
    return f"{code}\n\n{problem.test}\n"


def evaluate_solution(problem: Problem, code: str, timeout_s: float = 30) -> Outcome:
    """Run one candidate against the benchmark tests in the sandbox.

    The whole program is executed inside a single pytest function, so syntax errors and
    module-level assertion failures count as a failed test rather than a collection error.
    """
    program = build_program(problem, code)
    test_file = (
        f"PROGRAM = {program!r}\n\n\n"
        "def test_problem():\n"
        "    exec(compile(PROGRAM, 'candidate.py', 'exec'), {'__name__': 'candidate'})\n"
    )
    with tempfile.TemporaryDirectory(prefix="locali-eval-") as tmp:
        Path(tmp, "test_problem.py").write_text(test_file)
        result = run_pytest(Path(tmp), timeout_s=timeout_s, coverage=False)

    if result.timed_out:
        status = "timeout"
    elif result.passed == 1:
        status = "passed"
    elif result.failed or result.errors:
        status = "failed"
    else:
        status = "crashed"  # e.g. killed for exceeding memory: no report written
    return Outcome(
        passed=status == "passed",
        status=status,
        detail=result.output[-2000:],
        duration_s=result.duration_s,
    )


def _load(repo_revision: tuple[str, str], limit: int | None):
    from datasets import load_dataset

    repo, revision = repo_revision
    rows = load_dataset(repo, revision=revision, split="test")
    return rows.select(range(min(limit, len(rows)))) if limit else rows


def load_humaneval_plus(limit: int | None = None) -> list[Problem]:
    return [
        Problem(
            benchmark="humaneval_plus",
            task_id=r["task_id"],
            prompt=r["prompt"],
            entry_point=r["entry_point"],
            test=r["test"],
            reference_solution=r["prompt"] + r["canonical_solution"],
        )
        for r in _load(HUMANEVAL_PLUS, limit)
    ]


def _mbpp_entry_point(code: str, first_assert: str) -> str:
    defined = set(re.findall(r"^def\s+(\w+)\s*\(", code, re.MULTILINE))
    for name in re.findall(r"(\w+)\s*\(", first_assert):
        if name in defined:
            return name
    raise ValueError(f"cannot find entry point in: {first_assert}")


def load_mbpp_plus(limit: int | None = None) -> list[Problem]:
    problems = []
    for r in _load(MBPP_PLUS, limit):
        tests = r["test_list"]
        first_assert = (ast.literal_eval(tests) if isinstance(tests, str) else tests)[0]
        problems.append(
            Problem(
                benchmark="mbpp_plus",
                task_id=f"Mbpp/{r['task_id']}",
                # EvalPlus MBPP+ prompt: description plus one example assertion as a docstring.
                prompt=f'"""\n{r["prompt"]}\n{first_assert}\n"""\n',
                entry_point=_mbpp_entry_point(r["code"], first_assert),
                test=r["test"],
                reference_solution=r["code"],
            )
        )
    return problems
