"""In-distribution evaluation on the held-out test split of the fine-tuning mixture.

Prompts are the exact training prompts (the user turns of each test example); the reference is
the training answer. Groups in the test split never appear in training (split by seed problem).

- internal_t1: bug repair in the T1 format, scored by the problem's full original test suite
  (sandbox), exact fix (same AST as the original), bug location and answer format.
- internal_t2: test generation, scored against the T2 builder's injected faults.
- internal_t3: structured review (bug recall, clean specificity, tool-finding line recall).
"""

import ast
import json
import os
from dataclasses import dataclass
from pathlib import Path

from evaluation.client import Completion
from training.data.format import parse_repair_answer

MIX_DIR_ENV = "LOCALI_MIX_DIR"


@dataclass
class InternalItem:
    task_id: str
    group: str
    messages: list


def mix_test_rows() -> list[dict]:
    """Test split of the mixture: $LOCALI_MIX_DIR, else data/mix_v1, else searched under /kaggle/input."""
    candidates = [Path(os.environ[MIX_DIR_ENV]) / "test.jsonl"] if os.environ.get(MIX_DIR_ENV) else []
    candidates.append(Path("data/mix_v1/test.jsonl"))
    candidates += sorted(Path("/kaggle/input").rglob("test.jsonl")) if Path("/kaggle/input").exists() else []
    for path in candidates:
        if path.exists():
            return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    raise FileNotFoundError("mixture test split not found; set LOCALI_MIX_DIR")


def _same_ast(a: str, b: str) -> bool:
    try:
        return ast.dump(ast.parse(a)) == ast.dump(ast.parse(b))
    except SyntaxError:
        return False


class InternalRepairTask:
    name = "internal_t1"
    dataset = None

    def __init__(self, rows: list[dict] | None = None, suites: dict[str, str] | None = None):
        self._rows = rows
        self._suites = suites

    @property
    def excluded(self) -> dict[str, str]:
        return {}

    def load(self, limit: int | None = None) -> list[InternalItem]:
        rows = self._rows if self._rows is not None else mix_test_rows()
        items = [InternalItem(r["id"], r["group"], r["messages"]) for r in rows if r["task"] == "T1"]
        return items[:limit] if limit else items

    def messages(self, item: InternalItem) -> list[dict]:
        return item.messages[:-1]

    def reference(self, item: InternalItem) -> str:
        return item.messages[-1]["content"]

    def _suite(self, group: str) -> str | None:
        if self._suites is None:
            from datasets import load_dataset

            from training.data.t1_bugs import SOURCE, SOURCE_REVISION, best_suite

            rows = load_dataset(SOURCE, revision=SOURCE_REVISION, split="train")
            self._suites = {f"{SOURCE}:{r['task_id']}": best_suite(r) for r in rows}
        return self._suites.get(group)

    def score(self, item: InternalItem, completion: Completion, eval_timeout_s: float) -> dict:
        from training.data.t1_bugs import _run

        diagnosis, code = parse_repair_answer(completion.text)
        ref_diagnosis, ref_code = parse_repair_answer(self.reference(item))
        result = _run(code, self._suite(item.group) or "", eval_timeout_s)
        passed = not result.timed_out and result.passed > 0 and not (result.failed or result.errors)
        location = (diagnosis or {}).get("bug_location", "")
        return {
            "status": "passed" if passed else "timeout" if result.timed_out else "failed",
            "passed": passed,
            "exact_fix": _same_ast(code, ref_code),
            "location_correct": isinstance(location, str) and location.strip() == ref_diagnosis["bug_location"].strip(),
            "format_valid": diagnosis is not None,
            "code": code,
        }

    def metrics(self, records: list[dict]) -> dict:
        n = len(records)
        if not n:
            return {}

        def rate(key: str) -> float:
            return round(sum(bool(r[key]) for r in records) / n, 4)

        return {"pass@1": rate("passed"), "exact_fix_rate": rate("exact_fix"),
                "location_accuracy": rate("location_correct"), "format_valid_rate": rate("format_valid")}


INTERNAL_T1_TASK = InternalRepairTask()


class _InternalTask:
    """Shared loading for internal tasks: one training task's rows from the test split."""

    task_tag = ""
    dataset = None

    def __init__(self, rows: list[dict] | None = None):
        self._rows = rows

    @property
    def excluded(self) -> dict[str, str]:
        return {}

    def load(self, limit: int | None = None) -> list[InternalItem]:
        rows = self._rows if self._rows is not None else mix_test_rows()
        items = [InternalItem(r["id"], r["group"], r["messages"]) for r in rows if r["task"] == self.task_tag]
        return items[:limit] if limit else items

    def messages(self, item: InternalItem) -> list[dict]:
        return item.messages[:-1]

    def reference(self, item: InternalItem) -> str:
        return item.messages[-1]["content"]


def _norm_line(line: str) -> str:
    return " ".join(str(line).split())


class InternalReviewTask(_InternalTask):
    """internal_t3: structured review. Buggy pair items need a bug finding on the injected line;
    clean pair items must report no bug; tool-labelled items are scored by line recall."""

    name = "internal_t3"
    task_tag = "T3"

    def score(self, item: InternalItem, completion: Completion, eval_timeout_s: float) -> dict:
        from training.data.t3_review import parse_review_answer

        reference = json.loads(self.reference(item))["findings"]
        predicted = parse_review_answer(completion.text)
        valid = predicted is not None
        predicted = [f for f in (predicted or []) if isinstance(f, dict)]
        pred_bug_lines = {_norm_line(f.get("line", "")) for f in predicted if f.get("category") == "bug"}
        ref_bugs = [f for f in reference if f["category"] == "bug"]
        line_recall = None
        if ref_bugs:
            kind = "buggy"
            correct = valid and _norm_line(ref_bugs[0]["line"]) in pred_bug_lines
        elif item.task_id.endswith("-clean"):
            kind = "clean"
            correct = valid and not pred_bug_lines
        else:
            kind = "tool"
            ref_lines = {_norm_line(f["line"]) for f in reference}
            pred_lines = {_norm_line(f.get("line", "")) for f in predicted}
            line_recall = len(ref_lines & pred_lines) / len(ref_lines) if ref_lines else None
            correct = valid and (ref_lines <= pred_lines if ref_lines else not predicted)
        return {"status": "correct" if correct else "incorrect", "kind": kind, "correct": bool(correct),
                "format_valid": valid, "line_recall": line_recall, "findings": predicted}

    def metrics(self, records: list[dict]) -> dict:
        def rate(rows: list[dict]) -> float | None:
            return round(sum(r["correct"] for r in rows) / len(rows), 4) if rows else None

        buggy = [r for r in records if r["kind"] == "buggy"]
        clean = [r for r in records if r["kind"] == "clean"]
        recalls = [r["line_recall"] for r in records if r["kind"] == "tool" and r["line_recall"] is not None]
        return {
            "bug_recall": rate(buggy),
            "clean_specificity": rate(clean),
            "pair_accuracy": rate(buggy + clean),
            "tool_line_recall": round(sum(recalls) / len(recalls), 4) if recalls else None,
            "format_valid_rate": round(sum(r["format_valid"] for r in records) / len(records), 4) if records else None,
        }


class InternalTestgenTask(_InternalTask):
    """internal_t2: generated tests are run on the original function; the tests that pass are run
    against the same injected faults the T2 builder used (seeded by problem id)."""

    name = "internal_t2"
    task_tag = "T2"

    def score(self, item: InternalItem, completion: Completion, eval_timeout_s: float) -> dict:
        import random
        import re

        from evaluation.extract import extract_all_code, extract_code, trim_to_parseable
        from evaluation.tasks.testgen import _run_tests, split_asserts
        from training.data.mutate import enumerate_mutants
        from training.data.t2_tests import MAX_MUTANTS

        code = extract_code(item.messages[0]["content"])
        tests = "from solution import *\n" + split_asserts(trim_to_parseable(extract_all_code(completion.text)))
        on_correct = _run_tests(code, tests, False, eval_timeout_s)
        kept = on_correct.passed_tests
        collected = on_correct.passed + on_correct.failed + on_correct.errors
        mutants = enumerate_mutants(code)
        task_number = re.sub(r".*:", "", item.group)
        random.Random(f"t2-3407-{task_number}").shuffle(mutants)
        mutants = mutants[:MAX_MUTANTS]
        killed = 0
        if kept:
            for mutant in mutants:
                result = _run_tests(mutant.code, tests, False, eval_timeout_s, select=kept)
                killed += result.timed_out or result.passed < len(kept) or bool(result.failed or result.errors)
        return {"status": "has_valid_tests" if kept else "no_valid_tests", "tests_collected": collected,
                "tests_passed_on_correct": len(kept), "mutants_tried": len(mutants), "mutants_killed": int(killed),
                "correct": bool(mutants) and killed == len(mutants)}

    def metrics(self, records: list[dict]) -> dict:
        n = len(records)
        if not n:
            return {}
        collected = sum(r["tests_collected"] for r in records)
        tried = sum(r["mutants_tried"] for r in records)
        return {
            "any_valid_test_rate": round(sum(r["tests_passed_on_correct"] > 0 for r in records) / n, 4),
            "test_pass_rate": round(sum(r["tests_passed_on_correct"] for r in records) / collected, 4) if collected else None,
            "mutant_kill_rate": round(sum(r["mutants_killed"] for r in records) / tried, 4) if tried else None,
            "all_mutants_killed_rate": round(sum(r["correct"] for r in records) / n, 4),
        }


INTERNAL_T2_TASK = InternalTestgenTask()
INTERNAL_T3_TASK = InternalReviewTask()
