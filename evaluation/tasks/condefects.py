"""ConDefects (Python): repair of real wrong submissions to AtCoder, pre-registered in
docs/preregistration-repair.md.

Wu et al., 2023, "ConDefects: A New Dataset to Address the Data Leakage Concern for LLM-based Fault
Localization and Program Repair" (github.com/appmlk/ConDefects, data CC BY-SA 4.0). Each faulty
program is a submission that failed AtCoder's tests; the same person's accepted submission is its
fixed version. Programs read standard input and write standard output.

Layout: `<code root>/<contest>_<task>/Python/<submission id>/{faultyVersion,correctVersion}.py`,
`<test root>/<contest>/<TASK>/{in,out}/<name>` (ConDefects' `Tool/RunTest.py`), dates in
`<code root>/../date.txt`.

Every program runs in the Docker sandbox, with the task's tests mounted read-only at /data (some
tasks have hundreds of MB of tests): one pytest test per test case, each running the program in a
subprocess with a 10 s limit. Output matches when the lines are equal after stripping trailing
whitespace (the protocol's rule; ConDefects' own tool compares lines exactly).
"""

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from evaluation.client import Completion
from evaluation.extract import extract_code
from evaluation.passk import pass_at_k
from security.sandbox import run_pytest

SINCE = "2024-02-01"
TEST_TIMEOUT_S = 10
SHOWN_CHARS = 1000
MEMORY = "1g"

PROMPT = """Fix the bug in this program. It reads from standard input and writes to standard output.

```python
{program}```

This test fails.
Input:
{input}
Expected output:
{expected}
Actual output:
{actual}

Return the complete fixed program in a markdown code block."""

DRIVER = '''import json
import subprocess
import sys
from pathlib import Path

import pytest

DATA = Path("/data")
CASES = Path("cases.txt").read_text().splitlines()


def lines(text):
    return [line.rstrip() for line in text.rstrip().splitlines()]


def run(name):
    with open(DATA / "in" / name, "rb") as stdin:
        return subprocess.run([sys.executable, "program.py"], stdin=stdin, capture_output=True,
                              timeout={timeout})


@pytest.mark.parametrize("name", CASES)
def test_case(name):
    try:
        done = run(name)
    except subprocess.TimeoutExpired:
        pytest.fail("RESULT<<<" + json.dumps("time limit exceeded") + ">>>")
    actual = done.stdout.decode(errors="replace")
    if lines(actual) != lines((DATA / "out" / name).read_text(errors="replace")):
        error = done.stderr.decode(errors="replace").strip().splitlines()
        shown = actual if actual.strip() or not error else error[-1]
        pytest.fail("RESULT<<<" + json.dumps(shown[:{chars}]) + ">>>")
'''

_RESULT = re.compile(r"Failed: RESULT<<<(.*?)>>>")
_FAILED_CASE = re.compile(r"FAILED test_cases\.py::test_case\[(.+?)\]")


@dataclass
class DefectItem:
    task_id: str  # "<contest>_<task>/<submission id>"
    date: str
    faulty: str
    correct: str
    tests: str  # folder with in/ and out/, relative to the test root
    shown_input: str = ""
    shown_expected: str = ""
    shown_actual: str = ""


def case_folder(test_root: Path, task: str) -> Path | None:
    contest, letter = task.rsplit("_", 1)
    for candidate in (test_root / contest / letter.upper(), test_root / contest / "Ex"):
        if (candidate / "in").is_dir():
            return candidate
    return None


def candidates(code_root: Path, test_root: Path, since: str = SINCE, before: str | None = None) -> list[DefectItem]:
    """Python programs of the tasks dated `since` or later (and earlier than `before`, when given)."""
    dates = dict(line.split() for line in (code_root.parent / "date.txt").read_text().splitlines() if line.strip())
    items = []
    for task, date in sorted(dates.items()):
        folder = code_root / task / "Python"
        tests = case_folder(test_root, task)
        if date < since or (before is not None and date >= before) or not folder.is_dir() or tests is None:
            continue
        for sub in sorted(folder.iterdir(), key=lambda p: int(p.name)):
            items.append(DefectItem(f"{task}/{sub.name}", date, (sub / "faultyVersion.py").read_text(errors="replace"),
                                    (sub / "correctVersion.py").read_text(errors="replace"),
                                    tests.relative_to(test_root).as_posix()))
    return items


@dataclass
class TestRun:
    passed: int
    failed_cases: list[str]
    results: dict[str, str]  # failed case -> shown output (or error / time limit)
    total: int
    timed_out: bool


def run_cases(program: str, tests: Path, cases: list[str] | None = None) -> TestRun:
    """Run `program` on the test cases of `tests` (all, or the named ones) in the sandbox."""
    # Smallest input first, and pytest stops at the first failure (pytest.ini below): a program is
    # fixed only when every test passes, so the outcome is the same, and the first failure is the
    # smallest failing input, the one the prompt shows.
    names = cases or sorted((p.name for p in (tests / "in").iterdir()),
                            key=lambda n: ((tests / "in" / n).stat().st_size, n))
    with tempfile.TemporaryDirectory(prefix="locali-condefects-") as tmp:
        work = Path(tmp)
        (work / "cases.txt").write_text("\n".join(names))
        (work / "pytest.ini").write_text("[pytest]\naddopts = -x\n")
        (work / "program.py").write_text(program)
        (work / "test_cases.py").write_text(DRIVER.format(timeout=TEST_TIMEOUT_S, chars=SHOWN_CHARS))
        result = run_pytest(work, timeout_s=TEST_TIMEOUT_S * len(names) + 60, memory=MEMORY, coverage=False,
                            data=tests)
    failed = _FAILED_CASE.findall(result.output)
    shown = {}
    for block in result.output.split("_ test_case[")[1:]:
        name = block.split("]", 1)[0]
        match = _RESULT.search(block)
        if match:
            shown[name] = json.loads(match.group(1))
    return TestRun(result.passed, sorted(set(failed)), shown, len(names), result.timed_out)


def _cut(text: str) -> str:
    return text if len(text) <= SHOWN_CHARS else text[:SHOWN_CHARS] + "[...]"


def tests_root() -> Path:
    return Path(os.environ.get("CONDEFECTS_TESTS", "data/condefects/Test"))


def harness_check(item: DefectItem, root: Path) -> tuple[bool, str]:
    """Kept when the accepted version passes every test and the faulty one fails at least one; fills
    in the failing test shown in the prompt (the smallest input, ties by file name)."""
    tests = root / item.tests
    correct = run_cases(item.correct, tests)
    if correct.timed_out or correct.passed != correct.total:
        return False, f"accepted version fails {correct.total - correct.passed} of {correct.total} tests"
    case, reason = failing_test(item, tests)
    return case is not None, reason


def failing_test(item: DefectItem, tests: Path) -> tuple[str | None, str]:
    """(name of the failing test the prompt shows, "kept"), filling in the item's shown fields; or
    (None, reason) when the faulty version has no failing test."""
    faulty = run_cases(item.faulty, tests)
    if not faulty.failed_cases and not faulty.timed_out:
        return None, "faulty version passes every test"
    if not faulty.failed_cases:
        return None, "faulty version timed out as a whole"
    shown = min(faulty.failed_cases, key=lambda n: ((tests / "in" / n).stat().st_size, n))
    item.shown_input = _cut((tests / "in" / shown).read_text(errors="replace").rstrip("\n"))
    item.shown_expected = _cut((tests / "out" / shown).read_text(errors="replace").rstrip("\n"))
    actual = run_cases(item.faulty, tests, [shown]).results.get(shown, faulty.results.get(shown, ""))
    item.shown_actual = _cut(actual.rstrip("\n")) if actual.strip() else "(no output)"
    return shown, "kept"


class ConDefectsTask:
    """Items come from the harness-checked file written by experiments/scripts/condefects_check.py."""

    name = "condefects"
    dataset = ("appmlk/ConDefects", "43f0834a82c5")

    def __init__(self, items_file: Path = Path("experiments/results/4_final_checks/condefects/items.jsonl")):
        self.items_file = items_file

    @property
    def excluded(self) -> dict[str, str]:
        return {}

    def load(self, limit: int | None = None) -> list[DefectItem]:
        rows = [DefectItem(**json.loads(line)) for line in self.items_file.read_text().splitlines() if line.strip()]
        return rows[:limit] if limit else rows

    def messages(self, item: DefectItem) -> list[dict]:
        program = item.faulty if item.faulty.endswith("\n") else item.faulty + "\n"
        return [{"role": "user", "content": PROMPT.format(program=program, input=item.shown_input,
                                                          expected=item.shown_expected, actual=item.shown_actual)}]

    def score(self, item: DefectItem, completion: Completion, eval_timeout_s: float) -> dict:
        code = extract_code(completion.text)
        if not code.strip():
            return {"status": "invalid", "passed": False, "code": ""}
        run = run_cases(code, tests_root() / item.tests)
        passed = not run.timed_out and run.passed == run.total
        return {"status": "passed" if passed else "failed", "passed": passed, "tests_passed": run.passed,
                "tests_total": run.total, "code": code}

    def metrics(self, records: list[dict]) -> dict:
        n, passed = len(records), sum(r["passed"] for r in records)
        return {"pass@1": round(pass_at_k(n, passed, 1), 4) if n else None}

    def reference(self, item: DefectItem) -> str:
        return f"```python\n{item.correct}\n```"


def item_row(item: DefectItem) -> str:
    return json.dumps(asdict(item))
