"""T2 test-generation data: verified CodeRM unittest suites converted to compact pytest files.

The converter rewrites unittest.TestCase methods into module-level pytest functions with plain
asserts. Suites it cannot convert completely (setUp/tearDown, instance state, unknown assert
methods) are rejected rather than partially converted.
"""

import ast
import copy
import random
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from evaluation.tasks.testgen import testgen_prompt
from security.sandbox import run_pytest
from training.data.mutate import enumerate_mutants

_COMPARE = {
    "assertEqual": ast.Eq, "assertNotEqual": ast.NotEq, "assertListEqual": ast.Eq, "assertTupleEqual": ast.Eq,
    "assertDictEqual": ast.Eq, "assertSetEqual": ast.Eq, "assertSequenceEqual": ast.Eq,
    "assertIs": ast.Is, "assertIsNot": ast.IsNot, "assertIn": ast.In, "assertNotIn": ast.NotIn,
    "assertGreater": ast.Gt, "assertGreaterEqual": ast.GtE, "assertLess": ast.Lt, "assertLessEqual": ast.LtE,
}


class _Unsupported(Exception):
    pass


def _self_call(node: ast.AST) -> tuple[str, ast.Call] | None:
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "self"):
        return node.func.attr, node
    return None


def _msg(call: ast.Call, positional_index: int) -> ast.expr | None:
    if len(call.args) > positional_index:
        return call.args[positional_index]
    return next((k.value for k in call.keywords if k.arg == "msg"), None)


def _assert_for(name: str, call: ast.Call) -> ast.stmt:
    args = call.args
    if name in _COMPARE:
        return ast.Assert(ast.Compare(args[0], [_COMPARE[name]()], [args[1]]), _msg(call, 2))
    if name == "assertTrue":
        return ast.Assert(args[0], _msg(call, 1))
    if name == "assertFalse":
        return ast.Assert(ast.UnaryOp(ast.Not(), args[0]), _msg(call, 1))
    if name in ("assertIsNone", "assertIsNotNone"):
        op = ast.Is() if name == "assertIsNone" else ast.IsNot()
        return ast.Assert(ast.Compare(args[0], [op], [ast.Constant(None)]), _msg(call, 1))
    if name == "assertIsInstance":
        return ast.Assert(ast.Call(ast.Name("isinstance"), [args[0], args[1]], []), _msg(call, 2))
    if name == "assertCountEqual":
        def ordered(x):
            return ast.Call(ast.Name("sorted"), [x], [ast.keyword("key", ast.Name("repr"))])
        return ast.Assert(ast.Compare(ordered(args[0]), [ast.Eq()], [ordered(args[1])]), _msg(call, 2))
    if name == "assertAlmostEqual":
        keywords = {k.arg: k.value for k in call.keywords}
        if "delta" in keywords:
            tolerance = keywords["delta"]
        else:
            places = keywords.get("places", args[2] if len(args) > 2 else ast.Constant(7))
            if not isinstance(places, ast.Constant):
                raise _Unsupported(name)
            tolerance = ast.Constant(10 ** -places.value)
        approx = ast.Call(ast.Attribute(ast.Name("pytest"), "approx"), [args[1]], [ast.keyword("abs", tolerance)])
        return ast.Assert(ast.Compare(args[0], [ast.Eq()], [approx]), None)
    if name == "assertRaises" and len(args) >= 2:
        raises = ast.Call(ast.Attribute(ast.Name("pytest"), "raises"), [args[0]], [])
        return ast.With([ast.withitem(raises)], [ast.Expr(ast.Call(args[1], args[2:], call.keywords))])
    raise _Unsupported(name)


class _Rewriter(ast.NodeTransformer):
    def visit_Expr(self, node: ast.Expr):
        found = _self_call(node.value)
        return _assert_for(*found) if found else node

    def visit_With(self, node: ast.With):
        self.generic_visit(node)
        items = []
        for item in node.items:
            found = _self_call(item.context_expr)
            if found and found[0] == "assertRaises":
                raises = ast.Call(ast.Attribute(ast.Name("pytest"), "raises"), found[1].args[:1], [])
                items.append(ast.withitem(raises, item.optional_vars))
            elif found:
                raise _Unsupported(found[0])
            else:
                items.append(item)
        node.items = items
        return node


def unittest_to_pytest(suite: str, entry_point: str) -> str | None:
    """pytest version of a unittest suite for `entry_point`, or None if it cannot be fully converted."""
    try:
        tree = ast.parse(suite)
    except SyntaxError:
        return None
    imports, functions = [], []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = {getattr(node, "module", None), *(alias.name for alias in node.names)}
            if not names & {"unittest", "solution"}:
                imports.append(node)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant):
                    continue  # class docstring
                if not isinstance(item, ast.FunctionDef) or not item.name.startswith("test"):
                    return None  # setUp, helpers, class attributes: instance state not supported
                fn = copy.deepcopy(item)
                fn.args = ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[])
                try:
                    fn = _Rewriter().visit(fn)
                except (_Unsupported, IndexError):
                    return None
                if any(isinstance(n, ast.Name) and n.id == "self" for n in ast.walk(fn)):
                    return None
                functions.append(fn)
    if not functions:
        return None
    module = ast.Module(body=[*imports, *functions], type_ignores=[])
    body = ast.unparse(ast.fix_missing_locations(module))
    # The caller adds the exact `from solution import ...` line for the names the tests use.
    return ("import pytest\n" if "pytest." in body else "") + body + "\n"


SOURCE = "KAKA22/CodeRM-UnitTest"
LICENSE = "Apache-2.0 (tests generated by Llama-3.1-70B-Instruct; see data card)"
MAX_MUTANTS = 4  # pilot: selected tests already caught 88 % of 6 tried mutants
MIN_TESTS, MAX_TESTS = 3, 8
MAX_CHARS = 2400  # ~600 tokens, well inside the 768-token generation limit


def _entry_point(code: str, tests: str) -> str | None:
    names = [n.name for n in ast.parse(code).body if isinstance(n, ast.FunctionDef)]
    return next((name for name in names if re.search(rf"\b{re.escape(name)}\s*\(", tests)), None)


def _run(code: str, tests: str, timeout_s: float):
    with tempfile.TemporaryDirectory(prefix="locali-t2-") as tmp:
        Path(tmp, "solution.py").write_text(code)
        Path(tmp, "test_generated.py").write_text(tests)
        return run_pytest(Path(tmp), timeout_s=timeout_s, coverage=False)


def _select(tests_module: str, names: list[str], code: str) -> str:
    """Test file with only the named tests and exact imports (pytest only if used)."""
    tree = ast.parse(tests_module)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))
               and not (isinstance(n, ast.Import) and n.names[0].name == "pytest")]
    body = ast.unparse([*imports, *functions])
    used = {n.id for f in functions for n in ast.walk(f) if isinstance(n, ast.Name)}
    defined = [n.name for n in ast.parse(code).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    header = "import pytest\n" if "pytest." in body else ""
    header += f"from solution import {', '.join(name for name in defined if name in used)}\n"
    return f"{header}\n{body}\n"


def _example_for_seed(seed_obj, seed: int, timeout_s: float):
    stats = dict.fromkeys(["seeds_unconvertible", "seeds_tests_fail", "seeds_weak_suite", "seeds_used"], 0)
    entry = _entry_point(seed_obj.code, seed_obj.tests)
    converted = unittest_to_pytest(seed_obj.tests, entry) if entry else None
    if not converted:
        stats["seeds_unconvertible"] = 1
        return None, stats
    runnable = "from solution import *\n" + converted
    original = _run(seed_obj.code, runnable, timeout_s)
    if original.timed_out or original.failed or original.errors or not original.passed_tests:
        stats["seeds_tests_fail"] = 1
        return None, stats
    all_tests = [nid.split("::")[-1] for nid in original.passed_tests]
    mutants = enumerate_mutants(seed_obj.code)
    random.Random(f"t2-{seed}-{seed_obj.task_id}").shuffle(mutants)
    kills: dict[str, set[int]] = {name: set() for name in all_tests}
    for i, mutant in enumerate(mutants[:MAX_MUTANTS]):
        result = _run(mutant.code, runnable, timeout_s)
        survivors = {nid.split("::")[-1] for nid in result.passed_tests}
        if result.timed_out:
            survivors = set()  # a hang is caught by every test that ran
        for name in all_tests:
            if name not in survivors:
                kills[name].add(i)
    killable = set().union(*kills.values())
    if not killable:
        stats["seeds_weak_suite"] = 1
        return None, stats
    chosen, covered = [], set()
    while covered != killable and len(chosen) < MAX_TESTS:  # greedy set cover
        best = max((n for n in all_tests if n not in chosen), key=lambda n: len(kills[n] - covered))
        chosen.append(best)
        covered |= kills[best]
    for name in all_tests:  # fill with remaining tests in suite order, for edge cases
        if len(chosen) >= MIN_TESTS:
            break
        if name not in chosen:
            chosen.append(name)
    ordered = [n for n in all_tests if n in chosen]
    tests = _select(converted, ordered, seed_obj.code)
    while len(tests) > MAX_CHARS and len(ordered) > MIN_TESTS:
        ordered.pop()
        tests = _select(converted, ordered, seed_obj.code)
    if len(tests) > MAX_CHARS:
        stats["seeds_weak_suite"] = 1
        return None, stats
    final = _run(seed_obj.code, tests, timeout_s)  # the exact target file must pass as written
    if final.failed or final.errors or final.timed_out or final.passed != len(ordered):
        stats["seeds_tests_fail"] = 1
        return None, stats
    stats["seeds_used"] = 1
    return {
        "id": f"t2-{seed_obj.task_id}",
        "task": "T2",
        "source": f"{SOURCE}:{seed_obj.task_id}",
        "license": LICENSE,
        "entry_point": entry,
        "code": seed_obj.code,
        "tests": tests,
        "tests_total": len(all_tests),
        "tests_selected": len(ordered),
        "mutants_tried": min(MAX_MUTANTS, len(mutants)),
        "mutants_killed": len(set().union(*(kills[n] for n in ordered))),
    }, stats


def build_t2_examples(seeds, workers: int = 4, seed: int = 3407, timeout_s: float = 60):
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda s: _example_for_seed(s, seed, timeout_s), seeds))
    examples = [ex for ex, _ in results if ex]
    stats: dict[str, int] = {}
    for _, st in results:
        for key, value in st.items():
            stats[key] = stats.get(key, 0) + value
    stats["examples"] = len(examples)
    return examples, stats


def t2_messages(example: dict) -> list[dict]:
    return [
        {"role": "user", "content": testgen_prompt(example["entry_point"], example["code"])},
        {"role": "assistant", "content": f"```python\n{example['tests']}```"},
    ]
