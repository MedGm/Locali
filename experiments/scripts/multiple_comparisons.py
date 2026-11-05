"""Base vs fine-tuned with a correction for testing many tasks at once.

Two families per fine-tuned model, each with Holm's step-down correction:

- confirmatory: repair (HumanEvalFix) and test generation, the two outcomes the training data was
  built for from the first mixture on; these are the claims;
- exploratory: every other task both runs have, labelled as such.

    uv run python experiments/scripts/multiple_comparisons.py > experiments/results/multiple_comparisons/README.md
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paired_compare import OUTCOME, compare_tasks, mcnemar_exact

R = Path("experiments/results")
CONFIRMATORY = ("humanevalfix", "testgen")
PAIRS = {  # name: (base root, base model, fine-tune root, fine-tune model, explain dir names)
    "3B run D (default)": (R / "kaggle_coder_baselines_20261024/results", "qwen2.5-coder-3b",
                           R / "finetune_qwen25_3b_qlora_mixv3b_diag/results", "qwen2.5-coder-3b-ft-qlora-mixv3b-diag"),
    "3B run E": (R / "kaggle_coder_baselines_20261024/results", "qwen2.5-coder-3b",
                 R / "finetune_qwen25_3b_qlora_mixv3s/results", "qwen2.5-coder-3b-ft-qlora-mixv3s"),
    "1.5B QLoRA v2 (fast option)": (R / "kaggle_baselines_20261012/results", "qwen2.5-coder-1.5b",
                                    R / "finetune_qwen25_qlora_v2/results", "qwen2.5-coder-1.5b-ft-qlora"),
}
EXPLAIN = {"3B run D (default)": ("qwen2.5-coder-3b", "qwen2.5-coder-3b-ft-qlora-mixv3b-diag"),
           "3B run E": ("qwen2.5-coder-3b", "qwen2.5-coder-3b-ft-qlora-mixv3s"),
           "1.5B QLoRA v2 (fast option)": ("qwen2.5-coder-1.5b", "qwen2.5-coder-1.5b-ft-qlora-v2")}


def holm(ps: list[float]) -> list[float]:
    """Holm-adjusted p-values, in the input order."""
    order = sorted(range(len(ps)), key=ps.__getitem__)
    adjusted, running = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adjusted[i] = running
    return adjusted


def explain_row(base: str, ft: str) -> dict:
    def load(model):
        path = R / "explain_t4/results" / model / "samples.jsonl"
        return {json.loads(line)["task_id"]: json.loads(line)["passed"] for line in path.read_text().splitlines()}
    a, b = load(base), load(ft)
    only_a, only_b = sum(a[i] and not b[i] for i in a), sum(b[i] and not a[i] for i in a)
    return {"task": "humanevalexplain", "n": len(a), "a": sum(a.values()) / len(a), "b": sum(b.values()) / len(b),
            "only_a": only_a, "only_b": only_b, "p": mcnemar_exact(only_a, only_b)}


def fmt(row: dict, adjusted: float) -> str:
    delta = (row["b"] - row["a"]) * 100
    mark = ("**" if delta > 0 else "*") if adjusted < 0.05 else ""
    value = f"{mark}{row['b'] * 100:.1f}{mark}"
    return (f"| {row['task']} | {row['n']} | {row['a'] * 100:.1f} | {value} | {delta:+.1f} | "
            f"{row['only_a']} / {row['only_b']} | {row['p']:.2g} | {adjusted:.2g} |")


def main() -> None:
    print(__doc__.split("\n\n")[0].strip("\n"), "\n")
    print("Bold: significantly better after Holm within its family (adjusted p < 0.05); italic: "
          "significantly worse. Built by `experiments/scripts/multiple_comparisons.py`.\n")
    for name, (root_a, model_a, root_b, model_b) in PAIRS.items():
        rows = [r for task in OUTCOME if (r := compare_tasks(root_a, model_a, task, root_b, model_b, task))]
        rows.append(explain_row(*EXPLAIN[name]))
        print(f"## {name}\n")
        for family, keep in (("Confirmatory", lambda t: t in CONFIRMATORY), ("Exploratory", lambda t: t not in CONFIRMATORY)):
            part = [r for r in rows if keep(r["task"])]
            print(f"{family} ({len(part)} tests, Holm within the family)\n")
            print("| Task | n | Base % | Fine-tune % | Δ points | only base / only fine-tune | p | Holm p |")
            print("|---|---|---|---|---|---|---|---|")
            for row, adjusted in zip(part, holm([r["p"] for r in part]), strict=True):
                print(fmt(row, adjusted))
            print()


if __name__ == "__main__":
    main()
