"""Review agent: the fine-tuned model reviews each function in the T3 format it was trained on.

The code is redacted before it reaches the model. Every finding quotes the line it is about; that
quote must match a line of the function, which gives the finding its file and line number. A
finding quoting a line that is not there is dropped as hallucinated, and counted.
"""

import ast
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from backend.agents.context import function_context
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


def review_span(model: Model, rel: str, lines: list[str], first_line: int, result: ReviewResult,
                prompt_code: str | None = None) -> None:
    """Ask the model to review `lines` (starting at `first_line` of `rel`) and add located findings.
    prompt_code, when given, is what the model sees instead (more or less context around the lines);
    findings still have to quote one of `lines`."""
    code = prompt_code if prompt_code is not None else "\n".join(lines)
    found = parse_review_answer(model([{"role": "user", "content": review_prompt(redact(code))}]))
    if found is None:
        result.invalid += 1
        return
    for f in found:
        if not isinstance(f, dict):
            continue
        quoted = _norm(str(f.get("line", "")))
        match = next((i for i, line in enumerate(lines) if quoted and _norm(line) == quoted), None)
        if match is None:
            result.dropped += 1
            continue
        result.findings.append({
            "tool": "model", "rule": "review", "path": rel, "line": first_line + match,
            "category": f.get("category") if f.get("category") in CATEGORIES else "quality",
            "severity": f.get("severity") if f.get("severity") in SEVERITIES else "low",
            "message": redact(str(f.get("message", ""))),
        })


def review_functions(root: str | Path, model: Model, functions: list[tuple[str, str]] | None = None,
                     context: str = "function") -> ReviewResult:
    """context: how much code the model sees (backend.agents.context)."""
    root = Path(root)
    result = ReviewResult()
    targets = functions if functions is not None else all_functions(root)
    if context == "file":
        # one call per file; only findings inside the target functions count, as with the other settings
        for rel in dict.fromkeys(rel for rel, _ in targets):
            src = (root / rel).read_text()
            names = {func for r, func in targets if r == rel}
            spans = [range(n.lineno, n.end_lineno + 1) for n in ast.parse(src).body
                     if isinstance(n, ast.FunctionDef) and n.name in names]
            part = ReviewResult()
            review_span(model, rel, src.splitlines(), 1, part)
            result.findings += [f for f in part.findings if any(f["line"] in span for span in spans)]
            result.dropped += part.dropped
            result.invalid += part.invalid
        return result
    for rel, func in targets:
        src = (root / rel).read_text()
        node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == func)
        review_span(model, rel, src.splitlines()[node.lineno - 1:node.end_lineno], node.lineno, result,
                    prompt_code=function_context(root, rel, func, context))
    return result
