"""Code completion by infilling, in the style of HumanEval-Infilling (Bavarian et al., 2022).

From each HumanEval+ reference solution a contiguous span of up to three body lines is masked,
chosen deterministically from the middle of the function body (docstring excluded). The model
sees the code with <FILL_ME> and returns the missing lines; the completed program must pass the
HumanEval+ tests in the sandbox.

Chat-model leniencies, both recorded per sample:
- the answer is shifted so its first line matches the masked line's indentation;
- an answer that redefines the whole function is scored as that function (returned_full_function).
"""

import ast
import re
from dataclasses import dataclass

from evaluation.client import Completion
from evaluation.extract import extract_code
from evaluation.passk import pass_at_k
from evaluation.tasks.codegen import (
    EXCLUDED,
    HUMANEVAL_PLUS,
    Problem,
    evaluate_solution,
    load_humaneval_plus,
)

MARKER = "<FILL_ME>"


@dataclass(frozen=True)
class Infill:
    prefix: str
    middle: str
    suffix: str


def _body_line_numbers(code: str, entry_point: str) -> list[int]:
    lines = code.splitlines()
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.FunctionDef) and node.name == entry_point:
            body = node.body
            if isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str) and len(body) > 1:
                body = body[1:]
            start, end = body[0].lineno, node.end_lineno
            return [n for n in range(start, end + 1) if lines[n - 1].strip()]
    return [n for n in range(1, len(lines) + 1) if lines[n - 1].strip()]


def make_infill(problem: Problem) -> Infill:
    code = problem.reference_solution
    lines = code.splitlines(keepends=True)
    candidates = _body_line_numbers(code, problem.entry_point)
    k = max(1, min(3, len(candidates) - 2))
    start = (len(candidates) - k) // 2
    first, last = candidates[start], candidates[start + k - 1]
    return Infill("".join(lines[: first - 1]), "".join(lines[first - 1 : last]), "".join(lines[last:]))


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def reindent(block: str, first_indent: str) -> str:
    lines = block.splitlines()
    first = next((line for line in lines if line.strip()), "")
    shift = len(first_indent) - _indent(first)
    out = []
    for line in lines:
        if not line.strip():
            out.append(line)
        elif shift >= 0:
            out.append(" " * shift + line)
        else:
            out.append(line[min(-shift, _indent(line)) :])
    return "\n".join(out)


class CompletionTask:
    name = "completion"
    dataset = HUMANEVAL_PLUS

    @property
    def excluded(self) -> dict[str, str]:
        return {k: v for k, v in EXCLUDED.items() if k.startswith("HumanEval/")}

    def load(self, limit: int | None = None) -> list[Problem]:
        return load_humaneval_plus(limit)

    def messages(self, item: Problem) -> list[dict]:
        infill = make_infill(item)
        content = (
            f"Fill in the code at {MARKER} in the following Python code. "
            "Return only the missing lines, with their indentation, in a markdown code block.\n\n"
            f"```python\n{infill.prefix}{MARKER}\n{infill.suffix}```"
        )
        return [{"role": "user", "content": content}]

    def score(self, item: Problem, completion: Completion, eval_timeout_s: float) -> dict:
        infill = make_infill(item)
        answer = extract_code(completion.text, entry_point=item.entry_point)
        full_function = re.search(rf"^\s*def\s+{re.escape(item.entry_point)}\s*\(", answer, re.MULTILINE) is not None
        if full_function:
            program = answer
        else:
            first_masked = next(line for line in infill.middle.splitlines() if line.strip())
            fill = reindent(answer, " " * _indent(first_masked))
            program = f"{infill.prefix}{fill.rstrip()}\n{infill.suffix}"
        outcome = evaluate_solution(item, program, timeout_s=eval_timeout_s)
        return {
            "status": outcome.status,
            "passed": outcome.passed,
            "returned_full_function": full_function,
            "masked_lines": infill.middle.count("\n"),
            "code": program,
            "eval_duration_s": outcome.duration_s,
        }

    def metrics(self, records: list[dict]) -> dict:
        n, passed = len(records), sum(r["passed"] for r in records)
        return {
            "pass@1": round(pass_at_k(n, passed, 1), 4) if n else None,
            "full_function_rate": round(sum(r["returned_full_function"] for r in records) / n, 4) if n else None,
        }

    def reference(self, item: Problem) -> str:
        return f"```python\n{make_infill(item).middle}```"


COMPLETION_TASK = CompletionTask()
