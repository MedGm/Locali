"""Chat examples for the v3 realistic bugs (training/data/realistic_bugs.py).

Two formats, half of the problems each:

- "repair": the trained repair format (training/data/format.py) with the test error, answered with
  a one-line JSON diagnosis and the whole fixed code. The explanation is the first sentence of the
  teacher's own description of the bug it wrote.
- "benchmark": "Fix bugs in <function>." with the failing tests, answered with the fixed code only,
  the way repair requests are usually phrased (and the way HumanEvalFix asks).

The answer is always the whole original code, so the model learns to return a complete, correct
function rather than to patch one token.
"""

import ast
import difflib
import json
import re

from training.data.format import REPAIR_INSTRUCTION
from training.data.mix import _bucket

MAX_TEST_CHARS = 2500  # longer suites are left out of the benchmark format


def first_changed_line(fixed: str, buggy: str) -> str:
    """The first line of the buggy code that differs from the fixed code (or the line after a deletion)."""
    a, b = fixed.splitlines(), buggy.splitlines()
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag != "equal":
            return b[j1] if j1 < len(b) else b[-1]
    return ""


def bug_function(buggy: str, fixed: str) -> str:
    """Name of the function that contains the first change, else the last top-level function."""
    line = first_changed_line(fixed, buggy)
    lineno = buggy.splitlines().index(line) + 1 if line in buggy.splitlines() else -1
    functions = [n for n in ast.walk(ast.parse(buggy)) if isinstance(n, ast.FunctionDef)]
    holding = [f for f in functions if f.lineno <= lineno <= (f.end_lineno or f.lineno)]
    if holding:
        return min(holding, key=lambda f: (f.end_lineno or f.lineno) - f.lineno).name
    top = [n for n in ast.parse(buggy).body if isinstance(n, ast.FunctionDef)]
    return top[-1].name if top else "the code"


def first_sentence(text: str, limit: int = 240) -> str:
    match = re.match(r"(.+?[.!?])(\s|$)", text.strip())
    sentence = match.group(1) if match else text.strip()
    return sentence[:limit]


def v3_format(bug: dict) -> str:
    if len(bug["tests"]) > MAX_TEST_CHARS:
        return "repair"
    return "repair" if _bucket("v3-format", bug["source"], 2) == 0 else "benchmark"


def v3_messages(bug: dict, fmt: str) -> list[dict]:
    buggy, fixed = bug["buggy_code"].rstrip(), bug["fixed_code"].rstrip()
    if fmt == "benchmark":
        user = (f"Fix bugs in {bug_function(buggy, fixed)}.\n\n```python\n{buggy}\n```\n\n"
                f"These tests fail:\n```python\n{bug['tests'].strip()}\n```\n\n"
                "Return the complete fixed function in a markdown code block.")
        return [{"role": "user", "content": user}, {"role": "assistant", "content": f"```python\n{fixed}\n```"}]
    user = (f"The following Python function has a bug.\n\n```python\n{buggy}\n```\n\n"
            f"Running its tests gives:\n```\n{bug['error'].strip()}\n```\n\n{REPAIR_INSTRUCTION}")
    diagnosis = {"bug_location": first_changed_line(fixed, buggy), "bug_type": bug["kind"].replace("_", " "),
                 "explanation": first_sentence(bug.get("description", ""))}
    return [{"role": "user", "content": user},
            {"role": "assistant", "content": f"{json.dumps(diagnosis)}\n```python\n{fixed}\n```"}]
