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
from evaluation.extract import extract_code, sanitize
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
    """Run one candidate against the benchmark tests in the sandbox."""
    return run_program(build_program(problem, code), timeout_s)


def run_program(program: str, timeout_s: float = 60) -> Outcome:
    """Execute a complete program (solution + tests) in the sandbox.

    The whole program is executed inside a single pytest function, so syntax errors and
    module-level assertion failures count as a failed test rather than a collection error.
    """
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
        raw = extract_code(completion.text, entry_point=item.entry_point)
        code = sanitize(raw)
        outcome = evaluate_solution(item, code, timeout_s=eval_timeout_s)
        return {
            "status": outcome.status,
            "passed": outcome.passed,
            "code": code,
            "raw_code": raw,
            "eval_duration_s": outcome.duration_s,
        }

    def metrics(self, records: list[dict]) -> dict:
        n, passed = len(records), sum(r["passed"] for r in records)
        return {"pass@1": round(pass_at_k(n, passed, 1), 4) if n else None}

    def reference(self, item: Problem) -> str:
        return f"```python\n{item.reference_solution}\n```"


HUMANEVAL_PLUS_TASK = CodegenTask("humaneval_plus", HUMANEVAL_PLUS, load_humaneval_plus, "HumanEval/")


PLAN_INSTRUCTION = (
    "First write a short plan of how you will solve it (a few sentences), then give a "
    "self-contained Python script in a markdown code block."
)


@dataclass
class PlanCodegenTask(CodegenTask):
    """The same problems and scoring, but the answer starts with a short plan before the code.

    Tests whether the fine-tuned models lose HumanEval+ points because they answer with bare code
    (the base model explains first).
    """

    def messages(self, item: Problem) -> list[dict]:
        return [{"role": "user", "content": f"Solve the following problem.\n```\n{item.prompt.strip()}\n```\n\n{PLAN_INSTRUCTION}"}]


HUMANEVAL_PLUS_PLAN_TASK = PlanCodegenTask("humaneval_plus_plan", HUMANEVAL_PLUS, load_humaneval_plus, "HumanEval/")


KEEPDOC_INSTRUCTION = (
    "Please provide a self-contained Python script that solves the following problem in a markdown "
    "code block. Copy the function signature and its docstring, with the examples, unchanged, then "
    "write the body."
)


@dataclass
class KeepDocCodegenTask(CodegenTask):
    """The same problems and scoring; the answer must repeat the docstring before the body.

    The fine-tuned models drop the docstring in most answers (their training targets rarely have
    one); this checks whether keeping it in the answer recovers the HumanEval+ loss.
    """

    def messages(self, item: Problem) -> list[dict]:
        return [{"role": "user", "content": f"{KEEPDOC_INSTRUCTION}\n```\n{item.prompt.strip()}\n```\n"}]


HUMANEVAL_PLUS_KEEPDOC_TASK = KeepDocCodegenTask("humaneval_plus_keepdoc", HUMANEVAL_PLUS, load_humaneval_plus, "HumanEval/")
MBPP_PLUS_TASK = CodegenTask("mbpp_plus", MBPP_PLUS, load_mbpp_plus, "Mbpp/")


COMMENT_INSTRUCTION = (
    "Please provide a self-contained Python script that solves the following problem in a markdown "
    "code block. Before each step of the code, write a short comment that says what the step does."
)


@dataclass
class CommentStepsCodegenTask(CodegenTask):
    """The same problems and scoring; the answer should comment each step of the code.

    Capability study step 3: where a fine-tuned model's wrong answer and the base's right one part,
    the base often writes a step comment and the fine-tuned model a one-liner.
    """

    def messages(self, item: Problem) -> list[dict]:
        return [{"role": "user", "content": f"{COMMENT_INSTRUCTION}\n```\n{item.prompt.strip()}\n```\n"}]


HUMANEVAL_PLUS_COMMENTS_TASK = CommentStepsCodegenTask(
    "humaneval_plus_comments", HUMANEVAL_PLUS, load_humaneval_plus, "HumanEval/"
)


def scaffold_prefix(problem: Problem, fence: str) -> str:
    """Start of an answer that repeats the stub and opens a comment as the first line of the body."""
    return f"{fence}{problem.prompt.rstrip()}\n    # "


def english_prompt(problem: Problem) -> str:
    """A HumanEval+ prompt rewritten in the shape of an MBPP+ prompt: quoted English, no code.

    The signature is named inline and the docstring (with its examples) becomes the text. Other
    functions in the prompt (3 problems have a helper) cannot be put into words and stay as code.
    """
    tree = ast.parse(problem.prompt)
    helpers, target = [], None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == problem.entry_point:
            target = node
        elif not isinstance(node, (ast.Import, ast.ImportFrom)):
            helpers.append(ast.get_source_segment(problem.prompt, node))
    signature = f"{target.name}({ast.unparse(target.args)})"
    if target.returns is not None:
        signature += f" -> {ast.unparse(target.returns)}"
    text = f'"""\nWrite a Python function `{signature}`.\n{ast.get_docstring(target) or ""}\n"""\n'
    if helpers:
        text += "\n" + "\n\n".join(helpers) + "\n"
    return text


def stub_prompt(problem: Problem) -> str:
    """An MBPP+ prompt rewritten in the shape of a HumanEval+ prompt: a signature with a docstring.

    The argument names come from the reference solution; the docstring holds the same
    description and example assertion as the original prompt.
    """
    lines = problem.prompt.strip().strip('"').strip("\n").splitlines()
    target = next(n for n in ast.walk(ast.parse(problem.reference_solution))
                  if isinstance(n, ast.FunctionDef) and n.name == problem.entry_point)
    doc = "".join(f"    {line}\n" if line.strip() else "\n" for line in lines)
    return f'def {target.name}({ast.unparse(target.args)}):\n    """\n{doc}    """\n'


@dataclass
class FormatSwapCodegenTask(CodegenTask):
    """The same problems, tests and instruction; only the problem text changes shape.

    The fine-tuned models write in a different style when the prompt holds code (HumanEval+) than
    when it holds English (MBPP+); experiments/results/capability_study/step1_behaviour. These
    variants swap the two shapes to test whether the shape causes it.
    """

    rewrite: Callable[[Problem], str] = english_prompt

    def messages(self, item: Problem) -> list[dict]:
        return [{"role": "user", "content": f"{INSTRUCTION}\n```\n{self.rewrite(item).strip()}\n```\n"}]


HUMANEVAL_PLUS_ENGLISH_TASK = FormatSwapCodegenTask(
    "humaneval_plus_english", HUMANEVAL_PLUS, load_humaneval_plus, "HumanEval/", english_prompt)
MBPP_PLUS_STUB_TASK = FormatSwapCodegenTask("mbpp_plus_stub", MBPP_PLUS, load_mbpp_plus, "Mbpp/", stub_prompt)
