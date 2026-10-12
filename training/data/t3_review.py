"""T3 structured code review data, with labels from tests and static tools only.

Answer format: {"findings": [{"line": <affected line, verbatim>, "category": "bug"|"security"|
"quality", "severity": "high"|"medium"|"low", "message": <one sentence>}]}; an empty list is a valid
answer. Bug findings come from T1 mutants (the test-verified injected fault), paired with the
verified original labelled with no bug, so the model sees as many "no bug" cases as bug cases.
Security findings come from Bandit (medium or higher), quality findings from Ruff (pyflakes,
syntax errors, bugbear).
"""

import ast
import json
import re
import subprocess
import sys

from evaluation.tasks.security import bandit_findings

RUFF_RULES = "F,E7,E9,B"
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)

REVIEW_INSTRUCTION = (
    'Respond with only a JSON object {"findings": [...]} where each finding is '
    '{"line": "<the affected line, verbatim>", "category": "bug|security|quality", '
    '"severity": "high|medium|low", "message": "<one sentence>"}. '
    "Use an empty list if the code has no problems."
)


def review_prompt(code: str) -> str:
    return (
        "Review the following Python code for bugs, security issues and code-quality problems.\n\n"
        f"```python\n{code.rstrip()}\n```\n\n{REVIEW_INSTRUCTION}"
    )


def _ruff_severity(rule: str) -> str:
    if rule.startswith(("E9", "F82")):  # syntax errors, undefined names
        return "high"
    if rule.startswith("B"):
        return "medium"
    return "low"


def tool_findings(code: str) -> list[dict]:
    """Ruff + Bandit findings with the affected line verbatim, ordered by line."""
    try:
        ast.parse(code)
    except SyntaxError:
        return []
    lines = code.splitlines()
    found = []
    ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--isolated", "--no-cache", "--select", RUFF_RULES,
         "--output-format", "json", "--stdin-filename", "snippet.py", "-"],
        input=code, capture_output=True, text=True, check=False,
    )
    for r in json.loads(ruff.stdout or "[]"):
        row = r["location"]["row"]
        found.append((row, {"line": lines[row - 1], "category": "quality",
                            "severity": _ruff_severity(r["code"]), "message": r["message"]}))
    for b in bandit_findings(code) or []:
        row = b["line_number"]
        found.append((row, {"line": lines[row - 1], "category": "security",
                            "severity": b["severity"].lower(), "message": b["message"]}))
    unique, seen = [], set()
    for _, finding in sorted(found, key=lambda x: x[0]):
        key = (finding["line"], finding["message"])
        if key not in seen:
            seen.add(key)
            unique.append(finding)
    return unique


def t3_items_from_bug_pair(example: dict, message: str) -> tuple[dict, dict]:
    """A buggy item (injected fault + tool findings) and its verified original (tool findings only)."""
    bug = {"line": example["buggy_code"].splitlines()[example["line"] - 1], "category": "bug",
           "severity": "high", "message": message}
    common = {"group": example["source"], "source": example["source"], "license": "Apache-2.0"}
    buggy = {"id": f"t3-{example['id']}-buggy", "code": example["buggy_code"],
             "findings": [bug, *tool_findings(example["buggy_code"])], **common}
    clean = {"id": f"t3-{example['id']}-clean", "code": example["fixed_code"],
             "findings": tool_findings(example["fixed_code"]), **common}
    return buggy, clean


def t3_messages(item: dict) -> list[dict]:
    return [
        {"role": "user", "content": review_prompt(item["code"])},
        {"role": "assistant", "content": json.dumps({"findings": item["findings"]})},
    ]


def parse_review_answer(text: str) -> list[dict] | None:
    """Findings list from a review answer, or None if no {"findings": [...]} object is found."""
    text = _THINK.sub("", text)
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("findings"), list):
            return obj["findings"]
    return None
