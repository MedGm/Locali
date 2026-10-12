"""HumanEvalPack items asked in the fine-tuning prompt formats (format vs bug-type transfer check).

The fine-tuned adapter barely moved on humanevalfix / bugdetect but improved strongly on held-out
training problems. These two tasks keep the benchmark items and change only the prompt format, so
a paired comparison separates "the prompt format is unfamiliar" from "human-written bugs are
harder than injected ones". Task ids equal those of humanevalfix / bugdetect for cross-format pairing.

- humanevalfix_t1fmt: T1 repair prompt (buggy function, one failing test, its real error), T1
  answer (JSON diagnosis + fixed function); scored by the HumanEvalPack tests like humanevalfix.
  Errors come from running the buggy solution in the sandbox under pytest, as for the training
  data; they are precomputed (`python -m evaluation.tasks.format_transfer`) and committed, because
  Kaggle has no Docker.
- bugdetect_t3fmt: T3 review prompt on the same buggy / correct functions as bugdetect; "has a
  bug" means at least one finding with category "bug".
"""

import json
import re
import tempfile
from pathlib import Path

from evaluation.client import Completion
from evaluation.extract import sanitize
from evaluation.tasks.codegen import run_program
from evaluation.tasks.humanevalpack import (
    HUMANEVALPACK,
    DetectItem,
    PackItem,
    _import_lines,
    binary_detection_metrics,
    load_humanevalpack,
)
from training.data.format import parse_repair_answer, repair_prompt
from training.data.t3_review import parse_review_answer, review_prompt

ERRORS_FILE = Path(__file__).with_name("humanevalfix_errors.json")
TEST_NAME = "test_check"


def buggy_code(item: PackItem) -> str:
    imports = item.imports.strip()
    return (f"{imports}\n\n" if imports else "") + f"{item.declaration}{item.buggy_solution}"


def pytest_test(item: PackItem) -> str:
    """The `check` function plus a pytest test calling it (the module-level call is dropped)."""
    body = re.sub(rf"^check\({re.escape(item.entry_point)}\)\s*$", "", item.test.strip(), flags=re.MULTILINE)
    return f"{body.rstrip()}\n\n\ndef {TEST_NAME}():\n    check({item.entry_point})\n"


def compute_error(item: PackItem, timeout_s: float = 60) -> str:
    from security.sandbox import run_pytest
    from training.data.t1_bugs import failing_test_details

    with tempfile.TemporaryDirectory(prefix="locali-fmt-") as tmp:
        Path(tmp, "solution.py").write_text(f"{buggy_code(item)}\n")
        Path(tmp, "test_suite.py").write_text(f"{item.test_setup}\nfrom solution import *\n\n{pytest_test(item)}")
        result = run_pytest(Path(tmp), timeout_s=timeout_s, coverage=False)
    if result.timed_out:
        return f"Timeout: the test did not finish within {timeout_s:.0f} seconds"
    if not (result.failed or result.errors) and not result.output.strip():
        return "MemoryError: the process was killed for exceeding the memory limit"
    _, error = failing_test_details(result.output)
    return re.sub(r" at 0x[0-9a-f]+>", ">", error) or "AssertionError"


class T1FormatFixTask:
    name = "humanevalfix_t1fmt"
    dataset = HUMANEVALPACK

    def __init__(self, errors: dict[str, str] | None = None):
        self._errors = errors

    @property
    def excluded(self) -> dict[str, str]:
        return {}

    def errors(self) -> dict[str, str]:
        if self._errors is None:
            self._errors = json.loads(ERRORS_FILE.read_text())
        return self._errors

    def load(self, limit: int | None = None) -> list[PackItem]:
        return load_humanevalpack(limit)

    def messages(self, item: PackItem) -> list[dict]:
        content = repair_prompt(buggy_code(item), TEST_NAME, pytest_test(item), self.errors()[item.task_id])
        return [{"role": "user", "content": content}]

    def score(self, item: PackItem, completion: Completion, eval_timeout_s: float) -> dict:
        diagnosis, raw = parse_repair_answer(completion.text)
        code = sanitize(raw)
        program = (
            f"{item.imports}\n{_import_lines(item.declaration)}\n{item.test_setup}\n\n"
            f"{code}\n\n{item.test}\n"
        )
        outcome = run_program(program, eval_timeout_s)
        return {"status": outcome.status, "passed": outcome.passed, "bug_type": item.bug_type,
                "format_valid": diagnosis is not None, "code": code, "eval_duration_s": outcome.duration_s}

    def metrics(self, records: list[dict]) -> dict:
        n = len(records)
        if not n:
            return {}
        by_type: dict[str, list[bool]] = {}
        for r in records:
            by_type.setdefault(r["bug_type"], []).append(r["passed"])
        return {
            "pass@1": round(sum(r["passed"] for r in records) / n, 4),
            "pass@1_by_bug_type": {k: round(sum(v) / len(v), 4) for k, v in sorted(by_type.items())},
            "format_valid_rate": round(sum(r["format_valid"] for r in records) / n, 4),
        }

    def reference(self, item: PackItem) -> str:
        diagnosis = {"bug_location": "", "bug_type": item.bug_type, "explanation": "reference"}
        return f"{json.dumps(diagnosis)}\n```python\n{item.declaration}{item.canonical_solution}```"


class ReviewFormatDetectTask:
    name = "bugdetect_t3fmt"
    dataset = HUMANEVALPACK

    def __init__(self, items: list[PackItem] | None = None):
        self._items = items

    @property
    def excluded(self) -> dict[str, str]:
        return {}

    @staticmethod
    def _items_from(pack: list[PackItem]) -> list[DetectItem]:
        items = []
        for p in pack:
            items.append(DetectItem(f"{p.task_id}/buggy", True, p.prompt + p.buggy_solution, p.bug_type))
            items.append(DetectItem(f"{p.task_id}/correct", False, p.prompt + p.canonical_solution, "none"))
        return items

    def load(self, limit: int | None = None) -> list[DetectItem]:
        return self._items_from(self._items if self._items is not None else load_humanevalpack(limit))

    def messages(self, item: DetectItem) -> list[dict]:
        return [{"role": "user", "content": review_prompt(item.spec_and_code)}]

    def score(self, item: DetectItem, completion: Completion, eval_timeout_s: float) -> dict:
        findings = parse_review_answer(completion.text)
        if findings is None:
            predicted, status = None, "invalid"
        else:
            predicted = any(isinstance(f, dict) and f.get("category") == "bug" for f in findings)
            status = "correct" if predicted == item.label else "incorrect"
        return {"status": status, "label": item.label, "predicted": predicted, "bug_type": item.bug_type,
                "findings": findings}

    def metrics(self, records: list[dict]) -> dict:
        return binary_detection_metrics(records)

    def reference(self, item: DetectItem) -> str:
        lines = [line for line in item.spec_and_code.splitlines() if line.strip()]
        findings = [{"line": lines[-1], "category": "bug", "severity": "high", "message": "reference"}] if item.label else []
        return json.dumps({"findings": findings})


T1_FORMAT_FIX_TASK = T1FormatFixTask()
REVIEW_FORMAT_DETECT_TASK = ReviewFormatDetectTask()


if __name__ == "__main__":
    from concurrent.futures import ThreadPoolExecutor

    pack = load_humanevalpack()
    with ThreadPoolExecutor(4) as pool:
        errors = dict(zip([p.task_id for p in pack], pool.map(compute_error, pack), strict=True))
    ERRORS_FILE.write_text(json.dumps(errors, indent=1, sort_keys=True) + "\n")
    print(f"{len(errors)} errors written to {ERRORS_FILE}")
