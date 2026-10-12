"""T1 bug-repair data: inject single faults into verified solutions, keep those a real test catches.

Source: KAKA22/CodeRM-UnitTest (Apache-2.0) — competitive-programming problems with a ground-truth
Python function and unittest suites annotated with FAR/FRR (false acceptance / rejection rate).

For each seed: the original must pass its suite in the sandbox; mutants (training.data.mutate)
are tried in a seeded order and kept only if at least one test fails, errors or times out on
them. Equivalent mutants (all tests still pass) are rejected. The failing test's source and its
real error message become part of the training input.
"""

import ast
import json
import random
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from security.sandbox import run_pytest
from training.data.mutate import enumerate_mutants

SOURCE = "KAKA22/CodeRM-UnitTest"
SOURCE_REVISION = "98879a4b7d98a66d8c0da9567b8c7eabe4e1f411"  # train split
LICENSE = "Apache-2.0"
MAX_TRIES_PER_SEED = 6

OPERATOR_DESCRIPTION = {
    "comparison_flip": "wrong comparison operator",
    "boolean_swap": "wrong boolean operator",
    "arithmetic_swap": "wrong arithmetic operator",
    "off_by_one": "off-by-one constant",
    "negate_condition": "inverted condition",
}


@dataclass
class Seed:
    task_id: str
    question: str
    code: str
    tests: str


def select_seeds(rows, n: int, seed: int = 3407, max_lines: int = 40) -> list[Seed]:
    """Up to n seeds: parseable functions of at most max_lines lines with an FRR = 0 suite."""
    candidates = []
    for r in rows:
        code = r["code_ground_truth"]
        if code.count("\n") + 1 > max_lines:
            continue
        try:
            tree = ast.parse(code)
        except SyntaxError:
            continue
        if not any(isinstance(node, ast.FunctionDef) for node in tree.body):
            continue
        suites = [s for s in json.loads(r["unit_tests"]) if s.get("FRR") == 0]
        if not suites:
            continue
        best = min(suites, key=lambda s: (s.get("FAR", 1.0), s["ut_id"]))
        candidates.append(Seed(str(r["task_id"]), r["question"], code, best["code"]))
    rng = random.Random(seed)
    return rng.sample(candidates, min(n, len(candidates)))


def _run(code: str, tests: str, timeout_s: float):
    with tempfile.TemporaryDirectory(prefix="locali-t1-") as tmp:
        Path(tmp, "solution.py").write_text(code)
        Path(tmp, "test_suite.py").write_text("from solution import *\n" + tests)
        return run_pytest(Path(tmp), timeout_s=timeout_s, coverage=False)


def failing_test_details(output: str) -> tuple[str | None, str]:
    """(Class::method of the first failing test, the error lines of that test) from pytest output."""
    match = re.search(r"^(?:FAILED|ERROR) [^:\s]+\.py::(\S+)", output, re.MULTILINE)
    name = match.group(1) if match else None
    lines = output.splitlines()
    header = name.replace("::", ".") if name else None
    start = 0
    if header:
        for i, line in enumerate(lines):
            if re.match(rf"^_+ {re.escape(header)} _+$", line.strip()):
                start = i + 1
                break
    errors = []
    for line in lines[start:]:
        if re.match(r"^_{3,} .+ _{3,}$", line.strip()):
            break  # next failure section
        if line.startswith("E "):
            errors.append(line[1:].strip())
    return name, "\n".join(errors[:8])


def _test_source(tests: str, name: str | None) -> str:
    if not name:
        return ""
    parts = name.split("::")
    try:
        tree = ast.parse(tests)
    except SyntaxError:
        return ""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == parts[0]:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and len(parts) > 1 and item.name == parts[1]:
                    return ast.get_source_segment(tests, item) or ""
    return ""


def _examples_for_seed(seed_obj: Seed, mutants_per_seed: int, seed: int, timeout_s: float):
    stats = {"seeds_original_failed": 0, "seeds_used": 0, "mutants_tried": 0,
             "mutants_equivalent": 0, "mutants_timeout": 0, "mutants_crashed": 0}
    original = _run(seed_obj.code, seed_obj.tests, timeout_s)
    if original.timed_out or original.failed or original.errors or original.passed == 0:
        stats["seeds_original_failed"] = 1
        return [], stats
    stats["seeds_used"] = 1
    mutants = enumerate_mutants(seed_obj.code)
    random.Random(f"{seed}-{seed_obj.task_id}").shuffle(mutants)
    examples = []
    for mutant in mutants[:MAX_TRIES_PER_SEED]:
        if len(examples) >= mutants_per_seed:
            break
        stats["mutants_tried"] += 1
        result = _run(mutant.code, seed_obj.tests, timeout_s)
        if result.timed_out:
            stats["mutants_timeout"] += 1
            name, error = None, f"TimeoutError: the test suite did not finish within {timeout_s:.0f} s"
        elif result.failed or result.errors:
            name, error = failing_test_details(result.output)
        elif result.passed < original.passed:
            stats["mutants_crashed"] += 1
            continue
        else:
            stats["mutants_equivalent"] += 1
            continue
        examples.append({
            "id": f"t1-{seed_obj.task_id}-{len(examples)}",
            "task": "T1",
            "source": f"{SOURCE}:{seed_obj.task_id}",
            "license": LICENSE,
            "operator": mutant.operator,
            "bug_type": OPERATOR_DESCRIPTION[mutant.operator],
            "line": mutant.line,
            "original_snippet": mutant.original,
            "mutated_snippet": mutant.replacement,
            "buggy_code": mutant.code,
            "fixed_code": seed_obj.code,
            "failing_test": {"name": name or "timeout", "code": _test_source(seed_obj.tests, name), "error": error},
        })
    return examples, stats


def build_examples(seeds: list[Seed], mutants_per_seed: int = 2, seed: int = 3407,
                   timeout_s: float = 60, workers: int = 4) -> tuple[list[dict], dict]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda s: _examples_for_seed(s, mutants_per_seed, seed, timeout_s), seeds))
    examples = [ex for exs, _ in results for ex in exs]
    stats: dict[str, int] = {}
    for _, s in results:
        for key, value in s.items():
            stats[key] = stats.get(key, 0) + value
    stats["examples"] = len(examples)
    return examples, stats
