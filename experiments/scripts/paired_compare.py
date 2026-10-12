"""Paired per-item comparison of two runs on the same tasks, with an exact McNemar test.

    uv run python experiments/scripts/paired_compare.py <runs root A> <model A> <runs root B> <model B>
    uv run python experiments/scripts/paired_compare.py <root A> <model A> <task A> <root B> <model B> <task B>

The second form pairs two different tasks over the same item ids (e.g. humanevalfix against
humanevalfix_t1fmt: same items, different prompt format).

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
    "internal_t1": lambda r: r["passed"],
    "internal_t2": lambda r: r["correct"],  # every injected fault caught
    "internal_t3": lambda r: r["correct"],
    "humanevalfix_t1fmt": lambda r: r["passed"],
    "bugdetect_t3fmt": lambda r: r["status"] == "correct",
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


def compare_tasks(root_a: Path, model_a: str, task_a: str, root_b: Path, model_b: str, task_b: str) -> dict | None:
    a, b = records(root_a, model_a, task_a), records(root_b, model_b, task_b)
    shared = sorted(set(a) & set(b))
    if not shared:
        return None
    ok_a, ok_b = OUTCOME[task_a], OUTCOME[task_b]
    only_a = sum(ok_a(a[i]) and not ok_b(b[i]) for i in shared)
    only_b = sum(ok_b(b[i]) and not ok_a(a[i]) for i in shared)
    return {"task": task_a if task_a == task_b else f"{task_a} vs {task_b}", "n": len(shared),
            "a": sum(ok_a(a[i]) for i in shared) / len(shared), "b": sum(ok_b(b[i]) for i in shared) / len(shared),
            "only_a": only_a, "only_b": only_b, "p": mcnemar_exact(only_a, only_b)}


def compare(root_a: Path, model_a: str, root_b: Path, model_b: str) -> list[dict]:
    rows = [compare_tasks(root_a, model_a, task, root_b, model_b, task) for task in OUTCOME]
    return [r for r in rows if r]


if __name__ == "__main__":
    if len(sys.argv) == 7:
        root_a, model_a, task_a, root_b, model_b, task_b = sys.argv[1:]
        results = [r for r in [compare_tasks(Path(root_a), model_a, task_a, Path(root_b), model_b, task_b)] if r]
    else:
        root_a, model_a, root_b, model_b = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), sys.argv[4]
        results = compare(root_a, model_a, root_b, model_b)
    print(f"| Task | n | {model_a} | {model_b} | Δ (points) | only A | only B | McNemar p |")
    print("|---|---|---|---|---|---|---|---|")
    for r in results:
        mark = " **" if r["p"] < 0.05 else ""
        print(f"| {r['task']} | {r['n']} | {r['a']*100:.1f} | {r['b']*100:.1f} | {(r['b']-r['a'])*100:+.1f}{mark.strip() and ' *'} "
              f"| {r['only_a']} | {r['only_b']} | {r['p']:.3g} |")
