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


def first_sentence(text: str) -> str:
    match = re.match(r"(.+?[.!?])(\s|$)", text.strip())
    return match.group(1) if match else text.strip()


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
                 "explanation": bug.get("diagnosis") or first_sentence(bug.get("description", ""))}
    return [{"role": "user", "content": user},
            {"role": "assistant", "content": f"{json.dumps(diagnosis)}\n```python\n{fixed}\n```"}]


# The teacher wrote each bug and a note on what it changed ("Changed x to y"). That note describes
# the edit from the bug-maker's side; a repair answer needs the reviewer's side: what is wrong in
# the code shown and what it should be. These rewrite it, check it, or fall back to a template.

MAX_DIAGNOSIS_CHARS = 320
_BUG_MAKER = re.compile(r"^(I\b|Changed|Removed|Added|Introduced|Replaced|Modified|Swapped|Omitted|Altered|"
                        r"Inserted|Deleted|Moved|Updated)\b", re.IGNORECASE)
_KEYWORDS = {"if", "else", "elif", "for", "while", "in", "return", "and", "or", "not", "is", "def", "None", "True",
             "False", "range", "len", "the", "self"}


def diagnosis_messages(buggy: str, fixed: str, note: str, kind: str) -> list[dict]:
    user = (
        f"A code reviewer looks at this buggy Python code:\n```python\n{buggy.strip()}\n```\n\n"
        f"The correct version is:\n```python\n{fixed.strip()}\n```\n\n"
        f"(Notes from whoever introduced the bug, a {kind.replace('_', ' ')}: {note.strip()})\n\n"
        "Write the reviewer's diagnosis of the buggy code in one or two short sentences: which line or "
        "construct is wrong, what it does wrong, and what it should do instead. Refer to the code as it is "
        "now, do not describe an edit (never start with 'Changed', 'Removed' or 'Added'). Reply with the "
        "diagnosis only."
    )
    return [{"role": "user", "content": user}]


def _identifiers(text: str, short: bool = False) -> set[str]:
    """Names in code or prose; one-letter names only when short=True (in prose, "a" is a word)."""
    return {w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text) if w not in _KEYWORDS and (short or len(w) > 1)}


def _named(text: str) -> set[str]:
    """Names a diagnosis mentions: longer words anywhere, any name inside backticks."""
    quoted = " ".join(re.findall(r"`([^`]+)`", text))
    return _identifiers(text) | _identifiers(quoted, short=True)


def accept_diagnosis(text: str, bug_line: str, changed: str = "") -> str | None:
    """The diagnosis if it is complete, short, written from the reviewer's side and about the bug."""
    text = " ".join(text.strip().strip('"').split())
    if not text or len(text) > MAX_DIAGNOSIS_CHARS or _BUG_MAKER.match(text):
        return None
    if not text.endswith((".", "!", "?")):
        return None
    if not (_named(text) & (_identifiers(bug_line, short=True) | _identifiers(changed, short=True))):
        return None
    return text


def template_diagnosis(bug_line: str, kind: str) -> str:
    return f"`{bug_line.strip()}` has a {kind.replace('_', ' ')} bug, so the tests fail; it is corrected below."


def changed_text(fixed: str, buggy: str) -> str:
    """The lines that differ between the two versions, from both sides."""
    a, b = fixed.splitlines(), buggy.splitlines()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag != "equal":
            out += a[i1:i2] + b[j1:j2]
    return "\n".join(out)
