"""Code-generation benchmarks: EvalPlus HumanEval+ and MBPP+.

Prompts follow EvalPlus' instruction format for chat models so scores are comparable with
published EvalPlus numbers (without its assistant-prefill line, which chat APIs do not support).
Solutions run inside the Docker sandbox, never on the host.
"""

import ast
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from evaluation.client import Completion
from evaluation.extract import extract_code
from evaluation.passk import pass_at_k
from security.sandbox import run_pytest

HUMANEVAL_PLUS = ("evalplus/humanevalplus", "d32357cf319e50e9c8d8dab5ea876c72b0fd321b")
MBPP_PLUS = ("evalplus/mbppplus", "b2d74c91837c3f2a20c1299ae98133cbe7cfa077")

# Problems whose official reference solution cannot pass under this harness. Excluded for every
# model so scores stay comparable. Evidence: experiments/results/harness_validation/README.md
EXCLUDED = {
    "HumanEval/32": "HF test calls _poly(*candidate(*inp), inp), unpacking a float: TypeError for any solution",
    "Mbpp/255": "one input yields 1.66M tuples of length 77; reference comparison needs >2 GiB, above the sandbox limit",
}

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


def evaluate_solution(problem: Problem, code: str, timeout_s: float = 60) -> Outcome:
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
    # limit applies before exclusion, so a limited run may hold one fewer problem
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
        if r["task_id"] not in EXCLUDED
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
        if f"Mbpp/{r['task_id']}" in EXCLUDED:
            continue
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


@dataclass
class CodegenTask:
    """HumanEval+ / MBPP+: generate a solution, run the benchmark tests in the sandbox."""

    name: str
    dataset: tuple[str, str]
    loader: Callable[[int | None], list[Problem]]
    id_prefix: str

    @property
    def excluded(self) -> dict[str, str]:
        return {k: v for k, v in EXCLUDED.items() if k.startswith(self.id_prefix)}

    def load(self, limit: int | None = None) -> list[Problem]:
        return self.loader(limit)

    def messages(self, item: Problem) -> list[dict]:
        return build_messages(item)

    def score(self, item: Problem, completion: Completion, eval_timeout_s: float) -> dict:
        code = extract_code(completion.text, entry_point=item.entry_point)
        outcome = evaluate_solution(item, code, timeout_s=eval_timeout_s)
        return {
            "status": outcome.status,
            "passed": outcome.passed,
            "code": code,
            "eval_duration_s": outcome.duration_s,
        }

    def metrics(self, records: list[dict]) -> dict:
        n, passed = len(records), sum(r["passed"] for r in records)
        return {"pass@1": round(pass_at_k(n, passed, 1), 4) if n else None}

    def reference(self, item: Problem) -> str:
        return f"```python\n{item.reference_solution}\n```"


HUMANEVAL_PLUS_TASK = CodegenTask("humaneval_plus", HUMANEVAL_PLUS, load_humaneval_plus, "HumanEval/")
MBPP_PLUS_TASK = CodegenTask("mbpp_plus", MBPP_PLUS, load_mbpp_plus, "Mbpp/")
