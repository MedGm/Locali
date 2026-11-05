"""Pre-registered check, part 1: unpack the ConDefects tests that are needed and run the harness check.

    uv run python experiments/scripts/condefects_check.py extract <Test.zip> <code root> <out dir>
    CONDEFECTS_TESTS=<out dir>/Test uv run python experiments/scripts/condefects_check.py check <code root>

extract: only the contests with Python bugs from 2024-02-01 on (the evaluation) and abc221 (the three
format-check programs from before 2023, docs/preregistration-repair.md).
check: a program is kept when its accepted version passes every test and its faulty version fails at
least one (evaluation/tasks/condefects.py::harness_check). Writes experiments/results/condefects/
items.jsonl (kept programs, with the failing test the prompt shows) and harness.json (counts and
the reason for every dropped program), before any model sees them.
"""

import json
import re
import sys
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from evaluation.tasks.condefects import SINCE, candidates, harness_check, item_row, tests_root

OUT = Path("experiments/results/condefects")
FORMAT_CHECK_CONTEST = "abc221"


def needed_contests(code_root: Path) -> set[str]:
    dates = dict(line.split() for line in (code_root.parent / "date.txt").read_text().splitlines() if line.strip())
    return {task.rsplit("_", 1)[0] for task, date in dates.items()
            if date >= SINCE and (code_root / task / "Python").is_dir()} | {FORMAT_CHECK_CONTEST}


def extract(archive: Path, code_root: Path, out: Path) -> None:
    contests = needed_contests(code_root)
    with zipfile.ZipFile(archive) as z:
        members = [m for m in z.namelist() if len(parts := m.split("/")) > 1 and parts[0] == "Test" and parts[1] in contests]
        print(f"{len(contests)} contests, {len(members)} files")
        for member in members:
            target = (out / member).resolve()
            if not target.is_relative_to(out.resolve()):
                raise ValueError(f"unsafe path in archive: {member}")
            z.extract(member, out)


def check(code_root: Path) -> None:
    root = tests_root()
    items = candidates(code_root, root)
    print(f"{len(items)} candidate programs")
    with ThreadPoolExecutor(max_workers=3) as pool:
        verdicts = list(pool.map(lambda item: harness_check(item, root), items))
    kept = [item for item, (ok, _) in zip(items, verdicts, strict=True) if ok]
    dropped = {item.task_id: reason for item, (ok, reason) in zip(items, verdicts, strict=True) if not ok}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "items.jsonl").write_text("".join(item_row(item) + "\n" for item in kept))
    summary = {"since": SINCE, "candidates": len(items), "kept": len(kept),
               "kept_tasks": len({i.task_id.split("/")[0] for i in kept}),
               "dropped_by_reason": dict(Counter(re.sub(r"\d+", "N", r) for r in dropped.values())),
               "dropped": dropped}
    (OUT / "harness.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "dropped"}, indent=2))


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    if command == "extract":
        extract(Path(args[0]), Path(args[1]), Path(args[2]))
    else:
        check(Path(args[0]))
