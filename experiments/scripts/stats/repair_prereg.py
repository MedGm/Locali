"""Pre-registered check, part 1: score the repair answers and apply the registered analysis.

    CONDEFECTS_TESTS=<tests> uv run python experiments/scripts/stats/repair_prereg.py score
    uv run python experiments/scripts/stats/repair_prereg.py analyse

score: every answer in experiments/results/4_final_checks/repair_prereg_t4/results/<benchmark>/<model> is run in
the Docker sandbox (3 at a time, as in the harness check). analyse: the comparisons of
docs/preregistration-repair.md, printed as Markdown.
"""

import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from multiple_comparisons import holm
from paired_compare import mcnemar_exact

from evaluation.rescore import rescore_run
from evaluation.tasks.condefects import ConDefectsTask
from evaluation.tasks.quixbugs import QuixBugsTask

RESULTS = Path("experiments/results/4_final_checks/repair_prereg_t4/results")
BASE3, BASE15 = "qwen2.5-coder-3b", "qwen2.5-coder-1.5b"
PRIMARY = (BASE3, "qwen2.5-coder-3b-ft-qlora-mixv3b-diag")
SECONDARY = [(BASE3, "qwen2.5-coder-3b-ft-qlora-mixv3s"), (BASE3, "qwen2.5-coder-3b-ft-qlora-mixv3b"),
             (BASE15, "qwen2.5-coder-1.5b-ft-qlora-v2")]
NAMES = {BASE3: "3B base", "qwen2.5-coder-3b-ft-qlora-mixv3b-diag": "run D", "qwen2.5-coder-3b-ft-qlora-mixv3s": "run E",
         "qwen2.5-coder-3b-ft-qlora-mixv3b": "run C", BASE15: "1.5B base", "qwen2.5-coder-1.5b-ft-qlora-v2": "1.5B QLoRA v2"}


def score() -> None:
    for task in (ConDefectsTask(), QuixBugsTask()):
        items = task.load()
        for run_dir in sorted((RESULTS / task.name).iterdir()):
            begin = time.time()
            summary = rescore_run(run_dir, task, items, workers=3)
            print(f"{time.strftime('%H:%M')} {task.name} {run_dir.name}: pass@1 {summary['metrics']['pass@1']} "
                  f"in {time.time() - begin:.0f}s", flush=True)


def outcomes(benchmark: str, model: str) -> dict[str, dict]:
    path = RESULTS / benchmark / model / "samples.jsonl"
    return {(r := json.loads(line))["task_id"]: r for line in path.read_text().splitlines() if line.strip()}


def paired(benchmark: str, base: str, ft: str, one_per_task: bool = False) -> dict:
    a, b = outcomes(benchmark, base), outcomes(benchmark, ft)
    ids = sorted(a)
    if one_per_task:  # the lowest submission id of each task
        first = {}
        for i in ids:
            task, sub = i.split("/")
            if task not in first or int(sub) < int(first[task].split("/")[1]):
                first[task] = i
        ids = sorted(first.values())
    only_a = sum(a[i]["passed"] and not b[i]["passed"] for i in ids)
    only_b = sum(b[i]["passed"] and not a[i]["passed"] for i in ids)
    n, pa, pb = len(ids), sum(a[i]["passed"] for i in ids), sum(b[i]["passed"] for i in ids)
    diff = (pb - pa) / n
    # 95 % interval for a paired difference of proportions (Wald, with the discordant pairs)
    se = math.sqrt(max(only_a + only_b - (only_b - only_a) ** 2 / n, 0)) / n
    return {"n": n, "base": pa, "ft": pb, "only_base": only_a, "only_ft": only_b, "p": mcnemar_exact(only_a, only_b),
            "diff": diff, "low": diff - 1.96 * se, "high": diff + 1.96 * se}


def row(label: str, r: dict, adjusted: float | None = None) -> str:
    extra = f" | {adjusted:.2g}" if adjusted is not None else " | (one test)"
    return (f"| {label} | {r['n']} | {r['base']} | {r['ft']} | {r['only_base']} / {r['only_ft']} | "
            f"{r['diff'] * 100:+.1f} ({r['low'] * 100:+.1f} to {r['high'] * 100:+.1f}) | {r['p']:.2g}{extra} |")


def analyse() -> None:
    header = ("| Comparison | n | base fixed | fine-tune fixed | only base / only fine-tune | "
              "difference, points (95 % CI) | p | Holm p |\n|---|---|---|---|---|---|---|---|")
    print("Primary\n")
    print(header)
    print(row(f"ConDefects: {NAMES[PRIMARY[1]]} vs {NAMES[PRIMARY[0]]}", paired("condefects", *PRIMARY)))
    secondary = [(f"ConDefects: {NAMES[ft]} vs {NAMES[base]}", paired("condefects", base, ft)) for base, ft in SECONDARY]
    secondary += [(f"QuixBugs: {NAMES[ft]} vs {NAMES[base]}", paired("quixbugs", base, ft)) for base, ft in [PRIMARY, *SECONDARY]]
    print("\nSecondary (Holm together)\n")
    print(header)
    for (label, r), adjusted in zip(secondary, holm([r["p"] for _, r in secondary]), strict=True):
        print(row(label, r, adjusted))
    print("\nReported, not used for the decision: one program per task (lowest submission id)\n")
    print(header)
    print(row(f"ConDefects: {NAMES[PRIMARY[1]]} vs {NAMES[PRIMARY[0]]}", paired("condefects", *PRIMARY, one_per_task=True)))
    print("\nPer model\n\n| Model | ConDefects fixed (of 382) | cut off at 1,024 tokens | QuixBugs fixed (of 40) |\n|---|---|---|---|")
    for model, name in NAMES.items():
        c, q = outcomes("condefects", model), outcomes("quixbugs", model)
        print(f"| {name} | {sum(r['passed'] for r in c.values())} | {sum(r['finish_reason'] == 'length' for r in c.values())} "
              f"| {sum(r['passed'] for r in q.values())} |")


if __name__ == "__main__":
    score() if sys.argv[1] == "score" else analyse()
