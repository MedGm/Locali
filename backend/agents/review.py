"""Review agent: the fine-tuned model reviews each function in the T3 format it was trained on.

The code is redacted before it reaches the model. Every finding quotes the line it is about; that
quote must match a line of the function, which gives the finding its file and line number. A
finding quoting a line that is not there is dropped as hallucinated, and counted.
"""

import ast
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from backend.agents.files import is_test_file, python_files
from security.secrets import redact
from training.data.t3_review import parse_review_answer, review_prompt

Model = Callable[[list[dict]], str]
CATEGORIES = {"bug", "security", "quality"}
SEVERITIES = {"high", "medium", "low"}


@dataclass
class ReviewResult:
    findings: list[dict] = field(default_factory=list)
    dropped: int = 0  # findings whose quoted line is not in the function
    invalid: int = 0  # answers without a findings list


def all_functions(root: Path) -> list[tuple[str, str]]:
    out = []
    for path in python_files(root):
        rel = path.relative_to(root)
        if not is_test_file(rel):
            out += [(rel.as_posix(), n.name) for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)]
    return out


def _norm(line: str) -> str:
    return " ".join(line.split())


def review_functions(root: str | Path, model: Model, functions: list[tuple[str, str]] | None = None) -> ReviewResult:
    root = Path(root)
    result = ReviewResult()
    for rel, func in functions if functions is not None else all_functions(root):
        src = (root / rel).read_text()
        node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == func)
        lines = src.splitlines()[node.lineno - 1:node.end_lineno]
        found = parse_review_answer(model([{"role": "user", "content": review_prompt(redact("\n".join(lines)))}]))
        if found is None:
            result.invalid += 1
            continue
        for f in found:
            if not isinstance(f, dict):
                continue
            quoted = _norm(str(f.get("line", "")))
            match = next((i for i, line in enumerate(lines) if quoted and _norm(line) == quoted), None)
            if match is None:
                result.dropped += 1
                continue
            result.findings.append({
                "tool": "model", "rule": "review", "path": rel, "line": node.lineno + match,
                "category": f.get("category") if f.get("category") in CATEGORIES else "quality",
                "severity": f.get("severity") if f.get("severity") in SEVERITIES else "low",
                "message": redact(str(f.get("message", ""))),
            })
    return result
