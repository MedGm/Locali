"""Tables for capability study step 4 from the Kaggle job's answers (training/kaggle/evaluate/scaffold).

    uv run python experiments/scripts/stats/capability_step4.py experiments/results/3_finetune_3b/capability_study/step4_kaggle

Prints markdown: HumanEval+ pass@1 for each model, prompt condition and repetition penalty, paired
tests against the standard prompt and against the base, and the answers' style.
"""

import json
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from experiments.scripts.paired_compare import mcnemar_exact

NAMES = {"qwen2.5-coder-3b": "base", "qwen2.5-coder-3b-ft-qlora-mixv3b-diag": "D",
         "qwen2.5-coder-3b-ft-qlora-mixv3s": "E"}
CONDITIONS = ("standard", "comments", "scaffold")
PENALTIES = (1.05, 1.0)
LOST = ["HumanEval/54", "HumanEval/55", "HumanEval/83", "HumanEval/86", "HumanEval/89", "HumanEval/97",
        "HumanEval/100", "HumanEval/141", "HumanEval/144", "HumanEval/154"]


def body_comments(code: str) -> int:
    code = re.sub(r'(""".*?"""|\'\'\'.*?\'\'\')', "", code, flags=re.DOTALL)
    return sum(line.strip().startswith("#") for line in code.splitlines())


def paired(a: dict[str, bool], b: dict[str, bool]) -> str:
    only_a = sum(a[t] and not b[t] for t in a if t in b)
    only_b = sum(b[t] and not a[t] for t in a if t in b)
    return f"{only_a}/{only_b}, p {mcnemar_exact(only_a, only_b):.2g}"


def main(root: Path) -> None:
    rows = [json.loads(line) for line in (root / "answers.jsonl").read_text().splitlines() if line.strip()]
    runs: dict[tuple, dict[str, dict]] = {}
    for r in rows:
        runs.setdefault((r["model"], r["condition"], r["penalty"]), {})[r["task_id"]] = r
    passed = {k: {t: r["passed"] for t, r in v.items()} for k, v in runs.items()}
    n = len(next(iter(runs.values())))

    print(f"## HumanEval+ pass@1 ({n} problems), greedy\n")
    print("| Model | penalty | standard | comments | scaffold |")
    print("|---|---|---|---|---|")
    for m, name in NAMES.items():
        for pen in PENALTIES:
            cells = [f"{sum(passed[(m, c, pen)].values())} ({sum(passed[(m, c, pen)].values()) / n:.1%})"
                     for c in CONDITIONS if (m, c, pen) in passed]
            print(f"| {name} | {pen} | " + " | ".join(cells) + " |")

    print("\n## Against the same model's standard prompt, penalty 1.05 (only standard / only this, exact McNemar)\n")
    print("| Model | " + " | ".join(f"{c}, {p}" for p in PENALTIES for c in CONDITIONS if (c, p) != ("standard", 1.05))
          + " |")
    print("|---|" + "---|" * 5)
    for m, name in NAMES.items():
        ref = passed[(m, "standard", 1.05)]
        cells = [paired(ref, passed[(m, c, p)]) for p in PENALTIES for c in CONDITIONS if (c, p) != ("standard", 1.05)]
        print(f"| {name} | " + " | ".join(cells) + " |")

    print("\n## Against the base in the same condition (only base / only fine-tuned)\n")
    print("| Model | " + " | ".join(f"{c}, {p}" for p in PENALTIES for c in CONDITIONS) + " |")
    print("|---|" + "---|" * 6)
    base = next(iter(NAMES))
    for m, name in list(NAMES.items())[1:]:
        cells = []
        for p in PENALTIES:
            for c in CONDITIONS:
                b, f = passed[(base, c, p)], passed[(m, c, p)]
                cells.append(f"{(sum(f.values()) - sum(b.values())) / n:+.1%} ({paired(b, f)})")
        print(f"| {name} | " + " | ".join(cells) + " |")

    print("\n## Style, penalty 1.05: comment lines in the body per answer, output tokens, lost-10 passed\n")
    print("| Model | condition | comment lines | output tokens | lost-10 passed | cut off (length) |")
    print("|---|---|---|---|---|---|")
    for m, name in NAMES.items():
        for c in CONDITIONS:
            v = runs[(m, c, 1.05)]
            print(f"| {name} | {c} | {st.mean(body_comments(r['code']) for r in v.values()):.1f} "
                  f"| {st.mean(r['output_tokens'] for r in v.values()):.0f} "
                  f"| {sum(v[t]['passed'] for t in LOST if t in v)} "
                  f"| {sum(r['finish_reason'] == 'length' for r in v.values())} |")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
