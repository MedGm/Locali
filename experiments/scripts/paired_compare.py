"""Paired per-item comparison of two runs on the same tasks, with an exact McNemar test.

    uv run python experiments/scripts/paired_compare.py <runs root A> <model A> <runs root B> <model B>

For every task present in both, each item's binary outcome is compared: b = items only A got
right, c = items only B got right. The exact two-sided McNemar p-value is the binomial
probability of a split at least as uneven as (b, c) under p = 0.5.
"""

import json
import sys
from math import comb
from pathlib import Path

# task -> function(record) -> bool "success" (for securecodegen: not flagged)
OUTCOME = {
    "humaneval_plus": lambda r: r["passed"],
    "mbpp_plus": lambda r: r["passed"],
    "completion": lambda r: r["passed"],
    "humanevalfix": lambda r: r["passed"],
    "cruxeval_o": lambda r: r["passed"],
    "refactor": lambda r: r["behaviour_preserved"],
    "testgen": lambda r: r["caught_bug"],
    "bugdetect": lambda r: r["status"] == "correct",
    "vulndetect": lambda r: r["status"] == "correct",
    "securecodegen": lambda r: r["status"] == "clean",
}


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(comb(n, k) for k in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def records(root: Path, model: str, task: str) -> dict[str, dict]:
    runs = [d for d in (root / task).glob(f"{model}__*") if d.is_dir()]
    if not runs:
        return {}
    return {json.loads(line)["task_id"]: json.loads(line) for line in (runs[0] / "samples.jsonl").read_text().splitlines()}


def compare(root_a: Path, model_a: str, root_b: Path, model_b: str) -> list[dict]:
    rows = []
    for task, ok in OUTCOME.items():
        a, b = records(root_a, model_a, task), records(root_b, model_b, task)
        shared = sorted(set(a) & set(b))
        if not shared:
            continue
        only_a = sum(ok(a[i]) and not ok(b[i]) for i in shared)
        only_b = sum(ok(b[i]) and not ok(a[i]) for i in shared)
        rate_a = sum(ok(a[i]) for i in shared) / len(shared)
        rate_b = sum(ok(b[i]) for i in shared) / len(shared)
        rows.append({"task": task, "n": len(shared), "a": rate_a, "b": rate_b, "only_a": only_a,
                     "only_b": only_b, "p": mcnemar_exact(only_a, only_b)})
    return rows


if __name__ == "__main__":
    root_a, model_a, root_b, model_b = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), sys.argv[4]
    print(f"| Task | n | {model_a} | {model_b} | Δ (points) | only A | only B | McNemar p |")
    print("|---|---|---|---|---|---|---|---|")
    for r in compare(root_a, model_a, root_b, model_b):
        mark = " **" if r["p"] < 0.05 else ""
        print(f"| {r['task']} | {r['n']} | {r['a']*100:.1f} | {r['b']*100:.1f} | {(r['b']-r['a'])*100:+.1f}{mark.strip() and ' *'} "
              f"| {r['only_a']} | {r['only_b']} | {r['p']:.3g} |")
