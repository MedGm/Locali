"""Build the model-comparison tables (markdown) from scored run summaries.

    uv run python experiments/scripts/baseline_table.py experiments/results/kaggle_baselines_20261012/results \
        [more result roots ...]
"""

import json
import sys
from pathlib import Path

# task -> (headline metric, label, scale to percent)
HEADLINE = {
    "humaneval_plus": ("pass@1", "HumanEval+ pass@1", True),
    "mbpp_plus": ("pass@1", "MBPP+ pass@1", True),
    "completion": ("pass@1", "Completion (infilling) pass@1", True),
    "humanevalfix": ("pass@1", "Bug repair (HumanEvalFix) pass@1", True),
    "bugdetect": ("accuracy", "Bug detection accuracy (chance 50)", True),
    "cruxeval_o": ("pass@1", "Code reasoning (CRUXEval-O) pass@1", True),
    "testgen": ("bug_detection_rate", "Test generation: bugs caught", True),
    "refactor": ("behaviour_preserved_rate", "Refactoring: behaviour preserved", True),
    "securecodegen": ("insecure_rate", "Insecure generations, Bandit (lower is better)", True),
    "vulndetect": ("accuracy", "Vulnerability detection accuracy (chance 50, indicative)", True),
}
SECONDARY = {
    "testgen": [("test_pass_rate", "Test gen: generated tests correct"), ("mean_coverage_all", "Test gen: mean coverage")],
    "refactor": [("improved_rate", "Refactoring: improved and preserved")],
    "bugdetect": [("recall", "Bug detection: recall"), ("precision", "Bug detection: precision")],
    "vulndetect": [("recall", "Vuln detection: recall"), ("precision", "Vuln detection: precision")],
    "securecodegen": [("unparseable_rate", "Insecure gen: unparseable answers (not scanned)")],
}


def load(root: Path) -> dict[str, dict[str, dict]]:
    runs: dict[str, dict[str, dict]] = {}
    for summary in sorted(root.glob("*/*/summary.json")):
        task, model = summary.parent.parent.name, summary.parent.name.split("__")[0]
        runs.setdefault(model, {})[task] = json.loads(summary.read_text())
    return runs


def fmt(value, percent: bool) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}" if percent else f"{value:.2f}" if isinstance(value, float) else str(value)


def quality_table(runs: dict) -> str:
    models = sorted(runs)
    lines = ["| Task | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    for task, (key, label, pct) in HEADLINE.items():
        lines.append(f"| {label} | " + " | ".join(fmt(runs[m].get(task, {}).get("metrics", {}).get(key), pct) for m in models) + " |")
        for skey, slabel in SECONDARY.get(task, []):
            is_pct = "rate" in skey or skey in ("recall", "precision")
            cells = []
            for m in models:
                v = runs[m].get(task, {}).get("metrics", {}).get(skey)
                cells.append(fmt(v, is_pct) if is_pct else fmt(v, False))
            lines.append(f"| {slabel} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def efficiency_table(runs: dict) -> str:
    models = sorted(runs)
    rows = {
        "Mean output tokens (all tasks)": [],
        "Mean time to first token, s (16 concurrent)": [],
        "Mean decode tok/s per request (16 concurrent)": [],
        "GPU energy, kJ (all tasks)": [],
        "GPU energy per HumanEval+ task, J": [],
        "GPU energy per correct HumanEval+ solution, J": [],
        "Generation wall time, min (all tasks)": [],
    }
    for m in models:
        tasks = runs[m].values()
        tokens = [s["metrics"]["mean_output_tokens"] * s["metrics"]["n"] for s in tasks if s["metrics"].get("mean_output_tokens")]
        counts = [s["metrics"]["n"] for s in tasks if s["metrics"].get("mean_output_tokens")]
        rows["Mean output tokens (all tasks)"].append(f"{sum(tokens) / sum(counts):.0f}")
        ttft = [s["metrics"]["mean_ttft_s"] * s["metrics"]["n"] for s in tasks]
        rows["Mean time to first token, s (16 concurrent)"].append(f"{sum(ttft) / sum(s['metrics']['n'] for s in tasks):.2f}")
        decode = [s["metrics"]["mean_decode_tok_per_s"] for s in tasks if s["metrics"].get("mean_decode_tok_per_s")]
        rows["Mean decode tok/s per request (16 concurrent)"].append(f"{sum(decode) / len(decode):.1f}")
        energy = sum((s.get("gpu_energy") or {}).get("total_j") or 0 for s in tasks)
        rows["GPU energy, kJ (all tasks)"].append(f"{energy / 1000:.0f}")
        he = runs[m].get("humaneval_plus", {})
        he_j = (he.get("gpu_energy") or {}).get("total_j")
        passed = he.get("metrics", {}).get("status_counts", {}).get("passed")
        rows["GPU energy per HumanEval+ task, J"].append(f"{he_j / he['metrics']['n']:.0f}" if he_j else "—")
        rows["GPU energy per correct HumanEval+ solution, J"].append(f"{he_j / passed:.0f}" if he_j and passed else "—")
        wall = sum(s.get("this_session", {}).get("wall_s", 0) for s in tasks)
        rows["Generation wall time, min (all tasks)"].append(f"{wall / 60:.0f}")
    lines = ["| Measure | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    lines += [f"| {label} | " + " | ".join(values) + " |" for label, values in rows.items()]
    return "\n".join(lines)


if __name__ == "__main__":
    data: dict[str, dict[str, dict]] = {}
    for root in sys.argv[1:]:
        for model, tasks in load(Path(root)).items():
            data.setdefault(model, {}).update(tasks)
    print("## Quality (%)\n")
    print(quality_table(data))
    print("\n## Efficiency (Kaggle T4, FP16, vLLM, 16 concurrent requests)\n")
    print(efficiency_table(data))
