"""Debug agent: make failing tests pass by repairing the function they exercise.

For each failing test, the function under test is the repo function the test calls. The model gets
that function and the test in the benchmark-style repair prompt ("Fix bugs in f", answer: the code)
and its answer replaces only that function. The test is re-run in the sandbox; on failure the model
is asked again with its last version and the new error, sampled at a small temperature so it does
not repeat itself, up to `max_attempts` times. If no attempt passes, the file is restored. Once a
fix passes, a second short call asks what the bug was. All of this happens inside an agent
workspace; nothing here touches the user's folder.
"""

import ast
import difflib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from backend.agents.model import takes_temperature
from evaluation.extract import extract_code
from mcp_servers.tests_server import run_tests
from training.data.format import explain_fix_prompt, fix_prompt, parse_explanation
from training.data.t1_bugs import failing_test_details

RETRY_TEMPERATURE = 0.6  # the value measured in the feedback study (run B: 64 % -> 71 % in 3 attempts)

Model = Callable[[list[dict]], str]


@dataclass
class Fix:
    test: str
    file: str
    function: str
    fixed: bool
    attempts: int
    diagnosis: dict | None = None


def _module_file(root: Path, module: str) -> str | None:
    rel = module.replace(".", "/") + ".py"
    return rel if (root / rel).is_file() else None


def _test_node(tree: ast.Module, parts: list[str]) -> ast.FunctionDef | None:
    scope = tree.body
    for part in parts[:-1]:
        cls = next((n for n in scope if isinstance(n, ast.ClassDef) and n.name == part), None)
        if cls is None:
            return None
        scope = cls.body
    return next((n for n in scope if isinstance(n, ast.FunctionDef) and n.name == parts[-1]), None)


def target_of_test(root: str | Path, test_id: str) -> tuple[str, str] | None:
    """(file, function) of the first repo function the test calls, via the test module's imports."""
    root = Path(root)
    test_file, *parts = test_id.split("::")
    tree = ast.parse((root / test_file).read_text())
    imported = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and (rel := _module_file(root, node.module)):
            for alias in node.names:
                imported[alias.asname or alias.name] = (rel, alias.name)
    test = _test_node(tree, parts)
    if test is None:
        return None
    for node in ast.walk(test):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in imported:
            return imported[node.func.id]
    return None


def function_source(path: Path, name: str) -> str:
    src = path.read_text()
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(src, node)


def replace_function(path: Path, name: str, code: str) -> None:
    """Replace the top-level function `name` in `path` with the same-named function from `code`."""
    try:
        new = next(n for n in ast.parse(code).body if isinstance(n, ast.FunctionDef) and n.name == name)
    except (SyntaxError, StopIteration):
        raise ValueError(f"answer has no parseable function {name}") from None
    src = path.read_text()
    old = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == name)
    start = min([old.lineno, *(d.lineno for d in old.decorator_list)])
    lines = src.splitlines(keepends=True)
    new_src = "".join(code.splitlines(keepends=True)[min([new.lineno, *(d.lineno for d in new.decorator_list)]) - 1:
                                                     new.end_lineno])
    updated = "".join(lines[: start - 1]) + new_src.rstrip("\n") + "\n" + "".join(lines[old.end_lineno:])
    ast.parse(updated)
    path.write_text(updated)


def _test_source(root: Path, test_id: str) -> str:
    test_file, *parts = test_id.split("::")
    src = (root / test_file).read_text()
    node = _test_node(ast.parse(src), parts)
    return ast.get_source_segment(src, node) if node else ""


def _error(root: Path, test_id: str) -> str | None:
    result = run_tests(root, [test_id])
    if not result["failed"] and not result["errors"] and not result["timed_out"]:
        return None
    _, error = failing_test_details(result["output_tail"])
    return error or "the test failed"


def _first_changed_line(buggy: str, fixed: str) -> str:
    """The first line of the buggy function that the fix changes (or the line after an insertion)."""
    a, b = buggy.splitlines(), fixed.splitlines()
    for tag, i1, _i2, _j1, _j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag != "equal":
            return a[i1] if i1 < len(a) else a[-1]
    return ""


def _diagnose(model: Model, buggy: str, fixed: str) -> dict | None:
    found = parse_explanation(model([{"role": "user", "content": explain_fix_prompt(buggy, fixed)}]))
    return found and {"bug_location": _first_changed_line(buggy, fixed), **found}


def debug_failing_tests(root: str | Path, model: Model, max_attempts: int = 3,
                        retry_temperature: float = RETRY_TEMPERATURE) -> list[Fix]:
    root = Path(root)
    sampled = takes_temperature(model)
    fixes = []
    for test_id in run_tests(root)["failed"]:
        target = target_of_test(root, test_id)
        if target is None:
            continue
        rel, func = target
        path = root / rel
        original = path.read_text()
        buggy = function_source(path, func)
        shown, attempts = None, 0  # the first attempt sees the tests only, as in training
        error = _error(root, test_id)
        while error is not None and attempts < max_attempts:
            attempts += 1
            messages = [{"role": "user", "content": fix_prompt(func, function_source(path, func),
                                                               _test_source(root, test_id), shown)}]
            answer = model(messages, temperature=retry_temperature) if sampled and attempts > 1 else model(messages)
            try:
                replace_function(path, func, extract_code(answer, entry_point=func))
            except ValueError:
                shown = f"Your answer did not contain a valid `{func}` function."
                continue
            error = shown = _error(root, test_id)
        diagnosis = None
        if error is None and attempts:
            diagnosis = _diagnose(model, buggy, function_source(path, func))
        else:
            path.write_text(original)
        fixes.append(Fix(test_id, rel, func, error is None, attempts, diagnosis))
    return fixes
