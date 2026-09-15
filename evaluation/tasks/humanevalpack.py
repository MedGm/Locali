"""HumanEvalPack (Python) tasks: bug repair and bug detection.

Muennighoff et al., 2023, "OctoPack: Instruction Tuning Code Large Language Models".
Each problem has a human-written buggy solution next to the canonical one.

- humanevalfix: buggy function + its failing tests -> fixed function, checked in the sandbox
  (prompt adapted from OctoPack's HumanEvalFixTests variant).
- bugdetect: buggy or correct function with its specification -> {"has_bug": bool};
  precision / recall / F1 with "has a bug" as the positive class.
"""

import json
import re
from dataclasses import dataclass

from evaluation.client import Completion
from evaluation.extract import extract_code
from evaluation.passk import pass_at_k
from evaluation.tasks.codegen import run_program

HUMANEVALPACK = ("bigcode/humanevalpack", "9a41762f73a8cb23bb5811b73d5aab164efcf378")


@dataclass
class PackItem:
    task_id: str
    prompt: str
    declaration: str
    canonical_solution: str
    buggy_solution: str
    bug_type: str
    entry_point: str
    imports: str
    test_setup: str
    test: str


@dataclass
class DetectItem:
    task_id: str
    label: bool  # True: the shown implementation is buggy
    spec_and_code: str
    bug_type: str


def load_humanevalpack(limit: int | None = None) -> list[PackItem]:
    from datasets import load_dataset

    repo, revision = HUMANEVALPACK
    rows = load_dataset(repo, "python", revision=revision, split="test")
    if limit:
        rows = rows.select(range(min(limit, len(rows))))
    return [
        PackItem(
            task_id=r["task_id"], prompt=r["prompt"], declaration=r["declaration"],
            canonical_solution=r["canonical_solution"], buggy_solution=r["buggy_solution"],
            bug_type=r["bug_type"], entry_point=r["entry_point"], imports=r["import"],
            test_setup=r["test_setup"], test=r["test"],
        )
        for r in rows
    ]


def _import_lines(code: str) -> str:
    return "\n".join(line for line in code.splitlines() if line.startswith(("import ", "from ")))


class FixTask:
    name = "humanevalfix"
    dataset = HUMANEVALPACK

    @property
    def excluded(self) -> dict[str, str]:
        return {}

    def load(self, limit: int | None = None) -> list[PackItem]:
        return load_humanevalpack(limit)

    def messages(self, item: PackItem) -> list[dict]:
        content = (
            f"Fix bugs in {item.entry_point}.\n\n"
            f"```python\n{item.declaration}{item.buggy_solution}```\n\n"
            f"These tests fail:\n```python\n{item.test.strip()}\n```\n\n"
            "Return the complete fixed function in a markdown code block."
        )
        return [{"role": "user", "content": content}]

    def score(self, item: PackItem, completion: Completion, eval_timeout_s: float) -> dict:
        code = extract_code(completion.text, entry_point=item.entry_point)
        program = (
            f"{item.imports}\n{_import_lines(item.declaration)}\n{item.test_setup}\n\n"
            f"{code}\n\n{item.test}\n"
        )
        outcome = run_program(program, eval_timeout_s)
        return {
            "status": outcome.status,
            "passed": outcome.passed,
            "bug_type": item.bug_type,
            "code": code,
            "eval_duration_s": outcome.duration_s,
        }

    def metrics(self, records: list[dict]) -> dict:
        n, passed = len(records), sum(r["passed"] for r in records)
        by_type: dict[str, list[bool]] = {}
        for r in records:
            by_type.setdefault(r["bug_type"], []).append(r["passed"])
        return {
            "pass@1": round(pass_at_k(n, passed, 1), 4) if n else None,
            "pass@1_by_bug_type": {k: round(sum(v) / len(v), 4) for k, v in sorted(by_type.items())},
        }

    def reference(self, item: PackItem) -> str:
        return f"```python\n{item.declaration}{item.canonical_solution}```"


_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def parse_verdict(text: str, key: str) -> bool | None:
    """Boolean `key` from the first JSON object that has it, else from `key: true/false` text."""
    text = _THINK.sub("", text)
    for match in re.finditer(r"\{[^{}]*\}", text):
        try:
            value = json.loads(match.group(0)).get(key)
        except (json.JSONDecodeError, AttributeError):
            continue
        if isinstance(value, bool):
            return value
    match = re.search(rf'"?{re.escape(key)}"?\s*[:=]\s*(true|false)', text, re.IGNORECASE)
    return match.group(1).lower() == "true" if match else None


def parse_has_bug(text: str) -> bool | None:
    return parse_verdict(text, "has_bug")


def binary_detection_metrics(records: list[dict]) -> dict:
    """Precision/recall/F1 with label True as the positive class.

    Unparseable answers (predicted None) count as "nothing reported": never a true or false
    positive, a false negative on positive items, and always wrong for accuracy.
    """
    tp = sum(r["label"] and r["predicted"] is True for r in records)
    fp = sum(not r["label"] and r["predicted"] is True for r in records)
    fn = sum(r["label"] and r["predicted"] is not True for r in records)
    correct = sum(r["predicted"] is not None and r["predicted"] == r["label"] for r in records)
    n = len(records)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "accuracy": round(correct / n, 4) if n else None,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "invalid_rate": round(sum(r["predicted"] is None for r in records) / n, 4) if n else None,
    }


class BugDetectTask:
    name = "bugdetect"
    dataset = HUMANEVALPACK

    @property
    def excluded(self) -> dict[str, str]:
        return {}

    def load(self, limit: int | None = None) -> list[DetectItem]:
        items = []
        for p in load_humanevalpack(limit):
            items.append(DetectItem(f"{p.task_id}/buggy", True, p.prompt + p.buggy_solution, p.bug_type))
            items.append(DetectItem(f"{p.task_id}/correct", False, p.prompt + p.canonical_solution, "none"))
        return items

    def messages(self, item: DetectItem) -> list[dict]:
        content = (
            "Review this Python function against its docstring specification. "
            "Does the implementation contain a bug?\n\n"
            f"```python\n{item.spec_and_code}```\n\n"
            'Answer with only a JSON object: {"has_bug": true or false, "reason": "<one sentence>"}'
        )
        return [{"role": "user", "content": content}]

    def score(self, item: DetectItem, completion: Completion, eval_timeout_s: float) -> dict:
        predicted = parse_has_bug(completion.text)
        if predicted is None:
            status = "invalid"
        else:
            status = "correct" if predicted == item.label else "incorrect"
        return {"status": status, "label": item.label, "predicted": predicted, "bug_type": item.bug_type}

    def metrics(self, records: list[dict]) -> dict:
        return binary_detection_metrics(records)

    def reference(self, item: DetectItem) -> str:
        return json.dumps({"has_bug": item.label, "reason": "reference label"})


FIX_TASK = FixTask()
BUG_DETECT_TASK = BugDetectTask()
