"""QuixBugs (Python), the secondary benchmark of docs/preregistration-repair.md, part 1.

Lin et al., 2017 (github.com/jkoppel/QuixBugs, MIT): 40 small programs, each with one bug in one
line, a corrected version and tests (JSON input/output pairs, or pytest functions for the graph
programs). Both versions are checked first: the corrected one must pass all its tests, the buggy one
fail at least one. Slow tests stay skipped, as in QuixBugs' own runner without --runslow.

The prompt shows the function and its first failing test, as a call with the expected result for
JSON tests or as the test function for the others, with pytest's assertion message.
"""

import ast
import json
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from evaluation.client import Completion
from evaluation.extract import extract_code
from evaluation.passk import pass_at_k
from security.sandbox import run_pytest

QUIXBUGS = ("jkoppel/QuixBugs", "4257f44b0ff1")
TIMEOUT_S = 120
SHOWN_CHARS = 1000

PROMPT = """Fix the bug in this function.

```python
{program}```

This test fails:
```python
{test}
```
Error:
{error}

Return the complete fixed function in a markdown code block."""

CONFTEST = """import pytest


def pytest_configure(config):
    pytest.use_correct = False
    pytest.run_slow = False
"""


@dataclass
class QuixItem:
    task_id: str
    buggy: str
    correct: str
    shown_test: str = ""
    shown_error: str = ""


def programs(root: Path) -> list[str]:
    return sorted(p.stem for p in (root / "python_programs").glob("*.py")
                  if not p.stem.endswith("_test") and p.stem != "node")


def run(root: Path, name: str, program: str) -> tuple[bool, str, bool]:
    """Run the tests of `name` on `program` in the sandbox: (all passed, pytest output, timed out)."""
    with tempfile.TemporaryDirectory(prefix="locali-quixbugs-") as tmp:
        work = Path(tmp)
        (work / "python_programs").mkdir()
        (work / "python_testcases").mkdir()
        (work / "conftest.py").write_text(CONFTEST)
        (work / "python_programs" / "__init__.py").write_text("")
        (work / "python_programs" / f"{name}.py").write_text(program)
        for helper in ("node.py", "load_testdata.py"):
            shutil.copy(root / "python_testcases" / helper, work / "python_testcases" / helper)
        shutil.copy(root / "python_testcases" / "node.py", work / "node.py")
        shutil.copy(root / "python_testcases" / f"test_{name}.py", work / "python_testcases" / f"test_{name}.py")
        if (root / "json_testcases" / f"{name}.json").exists():
            (work / "json_testcases").mkdir()
            shutil.copy(root / "json_testcases" / f"{name}.json", work / "json_testcases" / f"{name}.json")
        result = run_pytest(work, timeout_s=TIMEOUT_S, coverage=False, select=[f"python_testcases/test_{name}.py"])
    passed = not result.timed_out and result.failed == 0 and result.errors == 0 and result.passed > 0
    return passed, result.output, result.timed_out


_FAILURE = re.compile(r"_{3,} (test\w*)(?:\[(.*?)\])? _{3,}\n(.*?)(?=\n_{3,} |\n=+ short test summary)", re.DOTALL)


def first_failure(root: Path, name: str, output: str, timed_out: bool) -> tuple[str, str]:
    """The first failing test and its error; when the whole run timed out, the first test."""
    match = _FAILURE.search(output)
    if match:
        test, param, body = match.groups()
        error = "\n".join(line[1:].strip() for line in body.splitlines() if line.startswith("E "))
    else:
        source = (root / "python_testcases" / f"test_{name}.py").read_text()
        test = next(n.name for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name.startswith("test"))
        param = "input_data0" if (root / "json_testcases" / f"{name}.json").exists() else None
        error = "time limit exceeded" if timed_out else (output.strip().splitlines() or [""])[-1]
    json_file = root / "json_testcases" / f"{name}.json"
    if param is not None and json_file.exists():
        index = int(re.search(r"(\d+)", param).group(1)) if re.search(r"input_data(\d+)", param) else 0
        rows = [json.loads(line) for line in json_file.read_text().splitlines() if line.strip()]
        args, expected = rows[min(index, len(rows) - 1)]
        shown = f"assert {name}({', '.join(repr(a) for a in args)}) == {expected!r}"
    else:
        source = (root / "python_testcases" / f"test_{name}.py").read_text()
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == test)
        shown = ast.get_source_segment(source, node)
    cut = lambda text: text if len(text) <= SHOWN_CHARS else text[:SHOWN_CHARS] + "[...]"
    return cut(shown), cut(error)


def harness_check(root: Path, name: str) -> tuple[QuixItem | None, str]:
    buggy = (root / "python_programs" / f"{name}.py").read_text()
    correct = (root / "correct_python_programs" / f"{name}.py").read_text()
    ok, _, _ = run(root, name, correct)
    if not ok:
        return None, "corrected version fails its tests"
    ok, output, timed_out = run(root, name, buggy)
    if ok:
        return None, "buggy version passes its tests"
    test, error = first_failure(root, name, output, timed_out)
    return QuixItem(name, buggy, correct, test, error), "kept"


class QuixBugsTask:
    name = "quixbugs"
    dataset = QUIXBUGS

    def __init__(self, items_file: Path = Path("experiments/results/4_final_checks/quixbugs/items.jsonl"),
                 root: Path = Path("data/quixbugs")):
        self.items_file, self.root = items_file, root

    @property
    def excluded(self) -> dict[str, str]:
        return {}

    def load(self, limit: int | None = None) -> list[QuixItem]:
        rows = [QuixItem(**json.loads(line)) for line in self.items_file.read_text().splitlines() if line.strip()]
        return rows[:limit] if limit else rows

    def messages(self, item: QuixItem) -> list[dict]:
        program = item.buggy if item.buggy.endswith("\n") else item.buggy + "\n"
        return [{"role": "user", "content": PROMPT.format(program=program, test=item.shown_test, error=item.shown_error)}]

    def score(self, item: QuixItem, completion: Completion, eval_timeout_s: float) -> dict:
        code = extract_code(completion.text, entry_point=item.task_id)
        if not code.strip():
            return {"status": "invalid", "passed": False, "code": ""}
        passed, _, _ = run(self.root, item.task_id, code)
        return {"status": "passed" if passed else "failed", "passed": passed, "code": code}

    def metrics(self, records: list[dict]) -> dict:
        n, passed = len(records), sum(r["passed"] for r in records)
        return {"pass@1": round(pass_at_k(n, passed, 1), 4) if n else None}

    def reference(self, item: QuixItem) -> str:
        return f"```python\n{item.correct}\n```"


def item_row(item: QuixItem) -> str:
    return json.dumps(asdict(item))
