"""v3 repair data: realistic bugs written by a teacher model into verified solutions.

The v2 bugs are single-token mutations, and the fine-tune learned exactly those: on HumanEvalFix it
fixes operator bugs better than the 9B teacher but barely moves on missing or excess logic
(docs/retrospective.md). Here the teacher is asked for one bug of a given kind, the kind of mistake
a developer makes, and a candidate is kept only if

- it parses, keeps every function signature, and is not just the original with other comments,
- it changes at most MAX_CHANGED_LINES lines, and at most half of a short function (a bug, not
  a rewrite),
- the problem's own unit tests fail on it, while they pass on the original.

Comments are stripped from both versions, so a comment cannot point at the bug. The target of the
training example is the whole original function.
"""

import ast
import difflib
import io
import re
import tokenize

from evaluation.extract import extract_code

BUG_KINDS = {
    "missing_logic": ("leave out a statement or a whole branch the function needs (an edge-case check, an else "
                      "branch, an update inside a loop), as if the developer forgot it"),
    "excess_logic": ("add a statement or a branch that should not be there (an extra condition, an early return, an "
                     "extra update), as if the developer handled a case that does not exist, or handled one twice"),
    "wrong_condition": "make a condition subtly wrong (a comparison, a boolean combination, a boundary)",
    "off_by_one": "get a range, an index or a loop boundary wrong by one",
    "wrong_variable": "use the wrong variable in one place, one that exists and has a plausible name",
    "wrong_value": "use a wrong constant, initial value or default",
    "wrong_update": "update or accumulate a result incorrectly (wrong operation, wrong place, or at the wrong time)",
}
MAX_CHANGED_LINES = 6
# kinds that must change the program's structure, not just an expression on one line
STATEMENTS_REMOVED = {"missing_logic"}
STATEMENTS_ADDED = {"excess_logic"}

SYSTEM = "You are helping build a dataset of realistic programming mistakes for training a code-repair model."


def bug_messages(question: str, code: str, kind: str) -> list[dict]:
    user = (
        f"Problem:\n{question.strip()}\n\nA correct solution:\n```python\n{code.strip()}\n```\n\n"
        f"Introduce exactly one bug into this solution. The bug should {BUG_KINDS[kind]}. "
        "Make it the kind of mistake a competent developer could plausibly make, so the code still looks "
        "reasonable and still runs on simple inputs. Keep all function names and parameters unchanged. "
        "Do not add comments or anything else that points at the bug. The code you return must differ from "
        "the solution above.\n\n"
        "Reply with one line starting with `Bug:` that says what you changed and why it is wrong, then the "
        "complete modified code in one ```python block."
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def strip_comments(code: str) -> str:
    """The code without comments and without the blank lines they leave."""
    tokens = [t for t in tokenize.generate_tokens(io.StringIO(code).readline) if t.type != tokenize.COMMENT]
    text = tokenize.untokenize(tokens)
    return "\n".join(line.rstrip() for line in text.splitlines() if line.strip()) + "\n"


def changed_lines(original: str, candidate: str) -> int:
    """Lines removed or added, counting a replaced line once."""
    a, b = original.strip().splitlines(), candidate.strip().splitlines()
    changed = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag != "equal":
            changed += max(i2 - i1, j2 - j1)
    return changed


def _signatures(tree: ast.AST) -> dict[str, str]:
    return {node.name: ast.dump(node.args) for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def parse_reply(text: str) -> tuple[str, str]:
    """(the teacher's one-line description of the bug, the code), either possibly empty."""
    match = re.search(r"^\s*\**Bug:?\**:?\s*(.+)$", text, re.MULTILINE)
    return (match.group(1).strip() if match else ""), extract_code(text)


def _statements(tree: ast.AST) -> int:
    return sum(isinstance(node, ast.stmt) for node in ast.walk(tree))


def check_candidate(original: str, candidate: str, kind: str | None = None) -> tuple[bool, str]:
    """Static checks before the tests are run: (accepted, reason)."""
    try:
        new_tree = ast.parse(candidate)
    except SyntaxError:
        return False, "syntax error"
    old_tree = ast.parse(original)
    if ast.dump(new_tree) == ast.dump(old_tree):
        return False, "unchanged"
    if _signatures(new_tree) != _signatures(old_tree):
        return False, "signature changed"
    old_code = strip_comments(original)
    limit = min(MAX_CHANGED_LINES, max(2, len(old_code.splitlines()) // 2))
    if changed_lines(old_code, strip_comments(candidate)) > limit:
        return False, "too many changed lines"
    if kind in STATEMENTS_REMOVED and _statements(new_tree) >= _statements(old_tree):
        return False, "no statement removed"
    if kind in STATEMENTS_ADDED and _statements(new_tree) <= _statements(old_tree):
        return False, "no statement added"
    return True, "ok"


def unittest_program(code: str, tests: str) -> str:
    """One file that runs a unittest suite against the code; exit status 0 only if every test passes."""
    return (
        f"{code}\n\n{tests}\n\n"
        "import sys as _sys, unittest as _unittest\n"
        "_result = _unittest.main(exit=False, verbosity=0, argv=['x']).result\n"
        "if not _result.wasSuccessful():\n"
        "    _lines = (_result.failures + _result.errors)[0][1].strip().splitlines()\n"
        "    _first = [l for l in _lines if l[:1].isalpha() and not l.startswith('Traceback')]\n"
        "    raise SystemExit((_first or _lines)[0])\n"
    )
