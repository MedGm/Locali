"""Re-score repair answers with fence-independent code extraction (format-vs-content analysis).

    uv run python experiments/scripts/lenient_fix_rescore.py <samples.jsonl> ...

For each run (humanevalfix or humanevalfix_t1fmt samples), prints strict pass@1 (as recorded)
and lenient pass@1 (code recovered by evaluation.tasks.format_transfer.lenient_code, run against
the same HumanEvalPack tests), and writes <run>/lenient.json with per-item outcomes.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from evaluation.extract import sanitize
from evaluation.tasks.codegen import run_program
from evaluation.tasks.format_transfer import lenient_code
from evaluation.tasks.humanevalpack import _import_lines, load_humanevalpack

ITEMS = {p.task_id: p for p in load_humanevalpack()}


def lenient_pass(record: dict) -> bool:
    item = ITEMS[record["task_id"]]
    code = sanitize(lenient_code(record["completion"], item.entry_point))
    program = f"{item.imports}\n{_import_lines(item.declaration)}\n{item.test_setup}\n\n{code}\n\n{item.test}\n"
    return run_program(program, 60).passed


if __name__ == "__main__":
    for path in map(Path, sys.argv[1:]):
        records = [json.loads(line) for line in path.read_text().splitlines()]
        with ThreadPoolExecutor(4) as pool:
            lenient = list(pool.map(lenient_pass, records))
        outcome = {r["task_id"]: bool(ok or r["passed"]) for r, ok in zip(records, lenient, strict=True)}
        (path.parent / "lenient.json").write_text(json.dumps(outcome, indent=1, sort_keys=True) + "\n")
        strict = sum(r["passed"] for r in records) / len(records)
        print(f"{path.parent.parent.name}/{path.parent.name}: strict {strict:.3f}, "
              f"lenient {sum(outcome.values()) / len(records):.3f} (n={len(records)})")
