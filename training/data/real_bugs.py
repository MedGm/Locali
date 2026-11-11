"""Real bugs for training: wrong AtCoder submissions from before the evaluation's cut-off.

The teacher-written bugs raise HumanEvalFix by 12 points and real bugs (ConDefects, contests from
2024-02-01 on) by none. ConDefects also holds the contests before that date: the same kind of
program, written and fixed by people, from other tasks. This turns them into training rows in the
prompt of the real-bug check (evaluation/tasks/condefects.py): the faulty program and one failing
test as input / expected output / actual output, answered with the accepted program.

    uv run python -m training.data.real_bugs extract <Test.zip> <code root> <out dir>
    CONDEFECTS_TESTS=<out dir>/Test uv run python -m training.data.real_bugs collect <code root> data/real/bugs.jsonl

collect runs each faulty program in the Docker sandbox until its first failing test, then the
accepted program on that test; a bug is kept when the accepted program passes it. It appends to the
output and skips programs already there, so it can be stopped and started again.

Nothing here reads a task dated 2024-02-01 or later: the split is by date and by task, so no
training program shares a task with the evaluation.
"""

import json
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from evaluation.tasks.condefects import (
    SINCE,
    ConDefectsTask,
    DefectItem,
    candidates,
    failing_test,
    run_cases,
    tests_root,
)

MAX_CHARS = 6000  # prompt and answer together; longer rows would be cut by the 2,048-token training window


def older_contests(code_root: Path) -> set[str]:
    dates = dict(line.split() for line in (code_root.parent / "date.txt").read_text().splitlines() if line.strip())
    return {task.rsplit("_", 1)[0] for task, date in dates.items()
            if date < SINCE and (code_root / task / "Python").is_dir()}


def extract(archive: Path, code_root: Path, out: Path) -> None:
    contests = older_contests(code_root)
    with zipfile.ZipFile(archive) as z:
        members = [m for m in z.namelist() if len(parts := m.split("/")) > 1 and parts[0] == "Test" and parts[1] in contests]
        print(f"{len(contests)} contests, {len(members)} files")
        for member in members:
            target = (out / member).resolve()
            if not target.is_relative_to(out.resolve()):
                raise ValueError(f"unsafe path in archive: {member}")
            z.extract(member, out)


def messages(item: DefectItem) -> list[dict]:
    task = ConDefectsTask()
    return [*task.messages(item), {"role": "assistant", "content": task.reference(item)}]


def check(item: DefectItem, root: Path) -> str:
    """"kept" when the faulty program fails a test that the accepted program passes."""
    tests = root / item.tests
    shown, reason = failing_test(item, tests)
    if shown is None:
        return reason
    accepted = run_cases(item.correct, tests, [shown])
    return "kept" if accepted.passed == 1 and not accepted.timed_out else "accepted version fails the shown test"


def collect(code_root: Path, out: Path, workers: int = 3) -> None:
    root = tests_root()
    done = {json.loads(line)["task_id"] for line in out.read_text().splitlines()} if out.exists() else set()
    items = [i for i in candidates(code_root, root, since="0000", before=SINCE) if i.task_id not in done]
    todo = [i for i in items if len(i.faulty) + len(i.correct) <= MAX_CHARS]
    print(f"{len(done)} done, {len(items)} left, {len(todo)} short enough to try")
    out.parent.mkdir(parents=True, exist_ok=True)
    count, lock = [0, 0], threading.Lock()

    def one(item: DefectItem) -> None:
        try:
            verdict = check(item, root)
        except Exception as e:  # noqa: BLE001 - one broken program must not stop a run of hours
            verdict = f"error: {type(e).__name__}: {e}"[:200]
        with lock, out.open("a") as fh:
            fh.write(json.dumps(asdict(item) | {"verdict": verdict}) + "\n")
            count[0] += 1
            count[1] += verdict == "kept"
        if count[0] % 25 == 0:
            print(f"{time.strftime('%H:%M')} {count[0]}/{len(todo)} checked, {count[1]} kept", flush=True)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, todo))
    print(f"checked {count[0]}, kept {count[1]}")


if __name__ == "__main__":
    command, *rest = sys.argv[1:]
    if command == "extract":
        extract(Path(rest[0]), Path(rest[1]), Path(rest[2]))
    elif command == "collect":
        collect(Path(rest[0]), Path(rest[1]))
    else:
        sys.exit(__doc__)
