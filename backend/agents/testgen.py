"""Test-generation agent: regression tests for functions no existing test mentions.

The model writes tests in the T2 format it was fine-tuned on (the function "lives in solution.py");
the import is then pointed at the real module. Multi-assert tests are split so one wrong expectation
only costs itself. Tests are run in the sandbox against the current code:

- passing tests are kept, as a new test file in the workspace;
- failing tests are never added. A failed assertion on what the function returned means either a
  bug in the code or a wrong expectation, and the agent cannot tell which, so it is reported as a
  suspect for review. A test that crashes instead (None passed as a database connection, invalid
  fake data, a missing import) says nothing about the code; those are only counted.
- a function that produced a suspect keeps none of its tests: passing tests record what the code
  does today, and with a suspected bug that may be the bug itself.
"""

import ast
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from backend.agents.context import function_context
from backend.agents.files import is_test_file, python_files
from evaluation.extract import extract_all_code, trim_to_parseable
from evaluation.tasks.testgen import split_asserts, testgen_prompt
from mcp_servers.tests_server import run_tests
from training.data.t1_bugs import failing_test_details

Model = Callable[[list[dict]], str]


@dataclass
class Suspect:
    file: str
    function: str
    test: str
    error: str


@dataclass
class TestgenResult:
    files: list[str] = field(default_factory=list)
    suspects: list[Suspect] = field(default_factory=list)
    crashed: dict[str, int] = field(default_factory=dict)  # "file::function" -> crashed tests


def _is_assertion(error: str) -> bool:
    first = error.strip().splitlines()[0] if error.strip() else ""
    return first.startswith(("assert ", "AssertionError"))


def untested_functions(root: str | Path) -> list[tuple[str, str]]:
    root = Path(root)
    mentioned: set[str] = set()
    for path in python_files(root):
        if is_test_file(path.relative_to(root)):
            tree = ast.parse(path.read_text())
            mentioned |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            mentioned |= {a.asname or a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    found = []
    for path in python_files(root):
        rel = path.relative_to(root)
        if is_test_file(rel):
            continue
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.FunctionDef) and node.name not in mentioned and not node.name.startswith("_"):
                found.append((rel.as_posix(), node.name))
    return found


def _point_at_module(tests: str, module: str) -> str:
    tests = re.sub(r"^from solution import ", f"from {module} import ", tests, flags=re.MULTILINE)
    tests = re.sub(r"^import solution\b", f"import {module} as solution", tests, flags=re.MULTILINE)
    return f"from {module} import *  # noqa: F403\n{tests}"


def _test_names(src: str) -> list[str]:
    return [n.name for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name.startswith("test")]


def _drop_functions(src: str, names: set[str]) -> str:
    lines = src.splitlines(keepends=True)
    for node in sorted(ast.parse(src).body, key=lambda n: n.lineno, reverse=True):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
            del lines[start - 1:node.end_lineno]
    return "".join(lines)


def _segment(src: str, name: str) -> str:
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(src, node)


def generate_tests(root: str | Path, model: Model, functions: list[tuple[str, str]] | None = None,
                   context: str = "function") -> TestgenResult:
    """context: how much code the model sees (backend.agents.context)."""
    root = Path(root)
    result = TestgenResult()
    test_dir = "tests/" if (root / "tests").is_dir() else ""
    for rel, func in functions if functions is not None else untested_functions(root):
        prompt = testgen_prompt(func, function_context(root, rel, func, context).rstrip("\n") + "\n")
        tests = trim_to_parseable(extract_all_code(model([{"role": "user", "content": prompt}])))
        try:
            tests = _point_at_module(split_asserts(tests), rel[:-3].replace("/", "."))
            names = _test_names(tests)
        except SyntaxError:
            continue
        if not names:
            continue
        out_rel = f"{test_dir}test_locali_{func}.py"
        out = root / out_rel
        out.write_text(tests)
        failed = {t.split("::")[-1] for t in run_tests(root, [out_rel])["failed"]}
        for name in sorted(failed):
            _, error = failing_test_details(run_tests(root, [f"{out_rel}::{name}"])["output_tail"])
            if _is_assertion(error):
                result.suspects.append(Suspect(rel, func, _segment(tests, name), error))
            else:
                key = f"{rel}::{func}"
                result.crashed[key] = result.crashed.get(key, 0) + 1
        kept = _drop_functions(tests, failed)
        if any(s.file == rel and s.function == func for s in result.suspects) or not _test_names(kept):
            out.unlink()
            continue
        out.write_text(kept.rstrip("\n") + "\n")
        check = run_tests(root, [out_rel])
        if check["failed"] or check["errors"] or check["timed_out"]:  # flaky or broken: keep nothing
            out.unlink()
            continue
        result.files.append(out_rel)
    return result
