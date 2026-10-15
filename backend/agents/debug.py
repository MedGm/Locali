"""Debug agent: make failing tests pass by repairing the function they exercise.

For each failing test, the function under test is the repo function the test calls. The model gets
that function, the test and its real error in the T1 repair format it was fine-tuned on, and its
answer replaces only that function. The test is re-run in the sandbox; on failure the new error
goes back to the model, up to `max_attempts` times. If no attempt passes, the file is restored.
All of this happens inside an agent workspace; nothing here touches the user's folder.
"""

import ast
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from mcp_servers.tests_server import run_tests
from training.data.format import parse_repair_answer, repair_prompt
from training.data.t1_bugs import failing_test_details

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


def debug_failing_tests(root: str | Path, model: Model, max_attempts: int = 3) -> list[Fix]:
    root = Path(root)
    fixes = []
    for test_id in run_tests(root)["failed"]:
        target = target_of_test(root, test_id)
        if target is None:
            continue
        rel, func = target
        path = root / rel
        original = path.read_text()
        error, diagnosis, attempts = _error(root, test_id), None, 0
        while error is not None and attempts < max_attempts:
            attempts += 1
            prompt = repair_prompt(function_source(path, func), test_id.split("::")[-1],
                                   _test_source(root, test_id), error)
            diagnosis, code = parse_repair_answer(model([{"role": "user", "content": prompt}]))
            try:
                replace_function(path, func, code)
            except ValueError:
                error = f"Your answer did not contain a valid `{func}` function."
                continue
            error = _error(root, test_id)
        if error is not None:
            path.write_text(original)
        fixes.append(Fix(test_id, rel, func, error is None, attempts, diagnosis))
    return fixes
