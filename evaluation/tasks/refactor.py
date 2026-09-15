"""Refactoring: improve code quality without changing behaviour.

Items are HumanEval+ reference solutions. A refactoring counts only if the HumanEval+ tests still
pass in the sandbox. Quality is compared before/after with static analysis that parses but never
executes the code: cyclomatic complexity and maintainability index (Radon) and lint violations
(Ruff with its default rule set, repository config ignored).
"""

import ast
import json
import subprocess
import sys

from radon.complexity import cc_visit
from radon.metrics import mi_visit
from radon.raw import analyze

from evaluation.client import Completion
from evaluation.extract import extract_code
from evaluation.tasks.codegen import (
    EXCLUDED,
    HUMANEVAL_PLUS,
    Problem,
    evaluate_solution,
    load_humaneval_plus,
)


def quality_metrics(code: str) -> dict | None:
    try:
        ast.parse(code)
    except SyntaxError:
        return None
    complexity = 0
    for block in cc_visit(code):
        methods = getattr(block, "methods", None)
        complexity += sum(m.complexity for m in methods) if methods is not None else block.complexity
    lint = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--isolated", "--no-cache", "--output-format", "json",
         "--stdin-filename", "candidate.py", "-"],
        input=code, capture_output=True, text=True, check=False,
    )
    return {
        "cyclomatic_complexity": complexity,
        "maintainability_index": round(mi_visit(code, multi=True), 2),
        "ruff_violations": len(json.loads(lint.stdout or "[]")),
        "sloc": analyze(code).sloc,
    }


class RefactorTask:
    name = "refactor"
    dataset = HUMANEVAL_PLUS

    @property
    def excluded(self) -> dict[str, str]:
        return {k: v for k, v in EXCLUDED.items() if k.startswith("HumanEval/")}

    def load(self, limit: int | None = None) -> list[Problem]:
        return load_humaneval_plus(limit)

    def messages(self, item: Problem) -> list[dict]:
        content = (
            "Refactor the following Python code to improve readability and maintainability "
            "without changing its behaviour. Keep the same function name and signature. "
            "Return the complete refactored code in a markdown code block.\n\n"
            f"```python\n{item.reference_solution}```"
        )
        return [{"role": "user", "content": content}]

    def score(self, item: Problem, completion: Completion, eval_timeout_s: float) -> dict:
        code = extract_code(completion.text, entry_point=item.entry_point)
        outcome = evaluate_solution(item, code, timeout_s=eval_timeout_s)
        before, after = quality_metrics(item.reference_solution), quality_metrics(code)
        deltas = {
            f"delta_{key}": (round(after[key] - before[key], 2) if before and after else None)
            for key in ("cyclomatic_complexity", "maintainability_index", "ruff_violations", "sloc")
        }
        if not outcome.passed:
            status = "behaviour_changed"
        else:
            dcc, dmi, dlint = (deltas[f"delta_{k}"] for k in ("cyclomatic_complexity", "maintainability_index", "ruff_violations"))
            no_worse = dcc <= 0 and dlint <= 0 and dmi >= 0
            better = dcc < 0 or dlint < 0 or dmi > 0
            status = "preserved_improved" if no_worse and better else "preserved_not_improved"
        return {
            "status": status,
            "behaviour_preserved": outcome.passed,
            "test_status": outcome.status,
            "quality_before": before,
            "quality_after": after,
            **deltas,
            "code": code,
            "eval_duration_s": outcome.duration_s,
        }

    def metrics(self, records: list[dict]) -> dict:
        n = len(records)
        preserved = [r for r in records if r["behaviour_preserved"]]

        def mean_delta(key: str) -> float | None:
            values = [r[key] for r in preserved if r.get(key) is not None]
            return round(sum(values) / len(values), 2) if values else None

        return {
            "behaviour_preserved_rate": round(len(preserved) / n, 4) if n else None,
            "improved_rate": round(sum(r["status"] == "preserved_improved" for r in records) / n, 4) if n else None,
            "mean_delta_cyclomatic_complexity": mean_delta("delta_cyclomatic_complexity"),
            "mean_delta_maintainability_index": mean_delta("delta_maintainability_index"),
            "mean_delta_ruff_violations": mean_delta("delta_ruff_violations"),
        }

    def reference(self, item: Problem) -> str:
        return f"```python\n{item.reference_solution}```"


REFACTOR_TASK = RefactorTask()
