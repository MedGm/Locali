"""Unit-test generation, scored against a real bug.

Items come from HumanEvalPack (Python): each function has a canonical implementation and a
human-written buggy one. The model writes a pytest file for the specified function; the file is
run twice in the sandbox:

1. against the correct implementation: all tests must pass (validity), with line + branch
   coverage of `solution.py`;
2. against the buggy implementation: a valid test file that fails, errors, hangs or crashes has
   caught the bug (like a killed mutant in mutation testing).
"""

import tempfile
from pathlib import Path

from evaluation.client import Completion
from evaluation.extract import extract_code
from evaluation.tasks.humanevalpack import HUMANEVALPACK, PackItem, load_humanevalpack
from security.sandbox import run_pytest


def _solution_module(item: PackItem, body: str) -> str:
    return f"{item.imports}\n{item.prompt}{body}"


def _run_tests(solution: str, tests: str, coverage: bool | str, timeout_s: float):
    with tempfile.TemporaryDirectory(prefix="locali-testgen-") as tmp:
        Path(tmp, "solution.py").write_text(solution)
        Path(tmp, "test_generated.py").write_text(tests)
        return run_pytest(Path(tmp), timeout_s=timeout_s, coverage=coverage)


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
        tests = extract_code(completion.text)
        on_correct = _run_tests(
            _solution_module(item, item.canonical_solution), tests, "solution", eval_timeout_s
        )
        collected = on_correct.passed + on_correct.failed + on_correct.errors
        valid = (
            not on_correct.timed_out
            and on_correct.passed > 0
            and on_correct.failed == 0
            and on_correct.errors == 0
        )
        caught = False
        if valid:
            on_buggy = _run_tests(_solution_module(item, item.buggy_solution), tests, False, eval_timeout_s)
            all_passed = (
                not on_buggy.timed_out
                and on_buggy.passed == on_correct.passed
                and on_buggy.failed == 0
                and on_buggy.errors == 0
            )
            caught = not all_passed
        if not valid:
            status = "invalid_tests"
        else:
            status = "valid_caught_bug" if caught else "valid_missed_bug"
        return {
            "status": status,
            "valid": valid,
            "caught_bug": caught,
            "tests_collected": collected,
            "coverage_percent": on_correct.coverage_percent,
            "bug_type": item.bug_type,
            "code": tests,
            "eval_duration_s": on_correct.duration_s,
        }

    def metrics(self, records: list[dict]) -> dict:
        n = len(records)
        valid = [r for r in records if r["valid"]]
        caught = sum(r["caught_bug"] for r in records)
        coverage = [r["coverage_percent"] for r in valid if r["coverage_percent"] is not None]
        return {
            "valid_rate": round(len(valid) / n, 4) if n else None,
            "bug_detection_rate": round(caught / n, 4) if n else None,
            "bug_detection_rate_among_valid": round(caught / len(valid), 4) if valid else None,
            "mean_coverage_valid": round(sum(coverage) / len(coverage), 2) if coverage else None,
            "mean_tests_collected": round(sum(r["tests_collected"] for r in records) / n, 2) if n else None,
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
