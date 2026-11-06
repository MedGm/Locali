"""Harness check of QuixBugs (pre-registered check, part 1, secondary benchmark).

    uv run python experiments/scripts/stats/quixbugs_check.py data/quixbugs

Writes experiments/results/4_final_checks/quixbugs/items.jsonl (programs whose corrected version passes and buggy
version fails, with the failing test the prompt shows) and harness.json, before any model runs.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from evaluation.tasks.quixbugs import harness_check, item_row, programs

OUT = Path("experiments/results/4_final_checks/quixbugs")

if __name__ == "__main__":
    root = Path(sys.argv[1])
    names = programs(root)
    with ThreadPoolExecutor(max_workers=2) as pool:
        verdicts = list(pool.map(lambda n: harness_check(root, n), names))
    kept = [item for item, _ in verdicts if item]
    dropped = {n: reason for n, (item, reason) in zip(names, verdicts, strict=True) if item is None}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "items.jsonl").write_text("".join(item_row(i) + "\n" for i in kept))
    (OUT / "harness.json").write_text(json.dumps({"programs": len(names), "kept": len(kept), "dropped": dropped}, indent=2))
    print(len(names), "programs,", len(kept), "kept; dropped:", dropped)
