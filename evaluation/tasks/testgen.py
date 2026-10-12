"""Unit-test generation, scored against a real bug.

Items come from HumanEvalPack (Python): each function has a canonical implementation and a
human-written buggy one. The model writes a pytest file for the specified function. In the sandbox:

1. The file runs against the correct implementation. Tests that fail there assert a wrong
   expected value (the oracle problem) and are discarded; the surviving tests form the suite.
   Test functions with several top-level asserts are first split into one test per assert,
   so a single wrong expected value does not discard the other checks.
   `strict_valid` records whether every test passed.
2. The surviving suite reruns against the correct implementation for line + branch coverage of
   `solution.py`, and against the buggy implementation: any failure, error, hang or crash there
   means the suite caught the bug (like a killed mutant in mutation testing).

Discarding failing assertions before measuring follows common practice in LLM test-generation
studies; without it a single wrong expected value voids an otherwise useful suite.
"""

import ast
import copy
import tempfile
from pathlib import Path

from evaluation.client import Completion
from evaluation.extract import extract_all_code, python_blocks, trim_to_parseable
from evaluation.tasks.humanevalpack import HUMANEVALPACK, PackItem, load_humanevalpack
from security.sandbox import run_pytest


def _solution_module(item: PackItem, body: str) -> str:
    return f"{item.imports}\n{item.prompt}{body}"


def _run_tests(solution: str, tests: str, coverage: bool | str, timeout_s: float, select: list[str] | None = None):
    with tempfile.TemporaryDirectory(prefix="locali-testgen-") as tmp:
        Path(tmp, "solution.py").write_text(solution)
        Path(tmp, "test_generated.py").write_text(tests)
        return run_pytest(Path(tmp), timeout_s=timeout_s, coverage=coverage, select=select)


class TestGenTask:
    name = "testgen"
    dataset = HUMANEVALPACK
    __test__ = False  # not a pytest test class despite the name

    @property
    def excluded(self) -> dict[str, str]:
        return {}

    def load(self, limit: int | None = None) -> list[PackItem]:
        return load_humanevalpack(limit)

    def messages(self, item: PackItem) -> list[dict]:
        content = (
            f"Write pytest unit tests for the function `{item.entry_point}` below. "
            f"It lives in `solution.py`; import it with `from solution import {item.entry_point}`. "
            "Test the behaviour described in the docstring, including edge cases. "
            "Return a single Python test file in a markdown code block.\n\n"
            f"```python\n{item.prompt}{item.canonical_solution}```"
        )
        return [{"role": "user", "content": content}]

    def score(self, item: PackItem, completion: Completion, eval_timeout_s: float) -> dict:
        # Test files may be split over several blocks or cut off at the token limit: join the
        # blocks and keep every complete statement (both recorded, applied to all models).
        joined = extract_all_code(completion.text)
        trimmed = trim_to_parseable(joined)
        tests = split_asserts(trimmed)
        correct, buggy = (_solution_module(item, body) for body in (item.canonical_solution, item.buggy_solution))

        full = _run_tests(correct, tests, False, eval_timeout_s)
        collected = full.passed + full.failed + full.errors
        kept = full.passed_tests
        coverage, caught = None, False
        if kept:
            coverage = _run_tests(correct, tests, "solution", eval_timeout_s, select=kept).coverage_percent
            on_buggy = _run_tests(buggy, tests, False, eval_timeout_s, select=kept)
            caught = on_buggy.timed_out or on_buggy.passed < len(kept) or bool(on_buggy.failed or on_buggy.errors)
        if not kept:
            status = "no_valid_tests"
        else:
            status = "caught_bug" if caught else "missed_bug"
        return {
            "status": status,
            "strict_valid": bool(kept) and not full.timed_out and full.failed == 0 and full.errors == 0,
            "caught_bug": caught,
            "tests_collected": collected,
            "tests_passed_on_correct": len(kept),
            "coverage_percent": coverage,
            "multi_block": len(python_blocks(completion.text)) > 1,
            "trimmed": trimmed != joined.rstrip(),
            "asserts_split": tests != trimmed,
            "bug_type": item.bug_type,
            "code": tests,
            "eval_duration_s": full.duration_s,
        }

    def metrics(self, records: list[dict]) -> dict:
        n = len(records)
        if not n:
            return {}
        collected = sum(r["tests_collected"] for r in records)
        coverage = [r["coverage_percent"] for r in records if r["coverage_percent"] is not None]
        return {
            "strict_valid_rate": round(sum(r["strict_valid"] for r in records) / n, 4),
            "test_pass_rate": round(sum(r["tests_passed_on_correct"] for r in records) / collected, 4) if collected else None,
            "any_valid_test_rate": round(sum(r["tests_passed_on_correct"] > 0 for r in records) / n, 4),
            "bug_detection_rate": round(sum(r["caught_bug"] for r in records) / n, 4),
            "mean_coverage_valid": round(sum(coverage) / len(coverage), 2) if coverage else None,
            "mean_coverage_all": round(sum(coverage) / n, 2),
            "mean_tests_collected": round(collected / n, 2),
            "multi_block_rate": round(sum(bool(r.get("multi_block")) for r in records) / n, 4),
        }

    def reference(self, item: PackItem) -> str:
        """The benchmark's own check() tests, wrapped as a pytest file."""
        suite = f"{item.imports}\n{item.test_setup}\n{item.test}"
        return (
            "```python\n"
            "import solution\n\n"
            f"SUITE = {suite!r}\n\n\n"
            "def test_reference_suite():\n"
            "    exec(SUITE, dict(vars(solution)))\n"
            "```"
        )


TESTGEN_TASK = TestGenTask()


def _split_function(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list | None:
    """One test per top-level assert, each keeping the non-assert statements before it."""
    if not fn.name.startswith("test"):
        return None
    positions = [i for i, statement in enumerate(fn.body) if isinstance(statement, ast.Assert)]
    if len(positions) < 2:
        return None
    parts = []
    for k, index in enumerate(positions):
        setup = [st for st in fn.body[:index] if not isinstance(st, ast.Assert)]
        part = copy.deepcopy(fn)
        part.name = f"{fn.name}__a{k}"
        part.body = copy.deepcopy([*setup, fn.body[index]])
        parts.append(part)
    return parts


def split_asserts(code: str) -> str:
    """Split multi-assert test functions so one wrong expected value only discards itself.

    Equivalent to discarding individual failing assertions. Asserts nested in loops or
    context managers are left inside their function. Unparseable or unchanged code is
    returned as is.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    changed = False

    def rewrite(body: list) -> list:
        nonlocal changed
        out = []
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                parts = _split_function(node)
                if parts:
                    changed = True
                    out.extend(parts)
                    continue
            elif isinstance(node, ast.ClassDef):
                node.body = rewrite(node.body)
            out.append(node)
        return out

    tree.body = rewrite(tree.body)
    return ast.unparse(ast.fix_missing_locations(tree)) if changed else code
