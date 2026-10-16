"""Collect the experiment results into one JSON file for the web app's results page.

    uv run python experiments/scripts/export_results.py      # writes experiments/results/summary.json

Every number is computed from the per-item result files with the same outcome rules and exact
McNemar test as the reports (experiments/scripts/paired_compare.py), so the page and the reports
cannot drift apart. Re-run it after adding results.
"""

import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from paired_compare import OUTCOME, compare_tasks, records

R = Path(__file__).resolve().parents[2] / "experiments" / "results"
BENCHMARKS = ["humaneval_plus", "mbpp_plus", "humanevalfix", "bugdetect", "cruxeval_o", "testgen", "refactor",
              "completion", "securecodegen", "vulndetect"]
FORMAT_TASKS = ["humanevalfix_t1fmt", "bugdetect_t3fmt"]
INTERNAL = ["internal_t1", "internal_t2", "internal_t3", "internal_t4"]
LABELS = {
    "humaneval_plus": "HumanEval+", "mbpp_plus": "MBPP+", "humanevalfix": "HumanEvalFix",
    "bugdetect": "Bug detection", "cruxeval_o": "CRUXEval-O", "testgen": "Test generation (bug caught)",
    "refactor": "Refactoring (behaviour kept)", "completion": "Code completion", "securecodegen": "Secure code generation",
    "vulndetect": "Vulnerability detection", "humanevalfix_t1fmt": "HumanEvalFix, trained format",
    "bugdetect_t3fmt": "Bug detection, trained format", "internal_t1": "Repair (held-out training problems)",
    "internal_t2": "Test writing (held-out)", "internal_t3": "Code review (held-out)",
    "internal_t4": "Execution trace (held-out)",
}

# (label, results root, model id) for each system, per task family
BASE = {"bench": (R / "kaggle_baselines_20261012/results", "qwen2.5-coder-1.5b"),
        "format": (R / "format_transfer_qwen25_v1/results", "qwen2.5-coder-1.5b"),
        "internal": (R / "internal_eval_v2split/results", "qwen2.5-coder-1.5b")}
V1 = {"bench": (R / "finetune_qwen25_qlora_v1/results", "qwen2.5-coder-1.5b-ft-qlora"),
      "format": (R / "format_transfer_qwen25_v1/results", "qwen2.5-coder-1.5b-ft-qlora"),
      "internal": (R / "internal_eval_v2split/results", "qwen2.5-coder-1.5b-ft-qlora")}
V2 = {name: (R / f"finetune_qwen25_{name}_v2/results", f"qwen2.5-coder-1.5b-ft-{name}") for name in ("qlora", "lora16", "rslora")}
PHI_BASE = {"bench": (R / "kaggle_baselines_20261012/results", "phi-4-mini"),
            "format": (R / "internal_eval_phi4mini_v2split/results", "phi-4-mini"),
            "internal": (R / "internal_eval_phi4mini_v2split/results", "phi-4-mini")}
PHI_V2 = (R / "finetune_phi4mini_qlora_v2/results", "phi-4-mini-ft-qlora")


def family(task: str) -> str:
    return "bench" if task in BENCHMARKS else "format" if task in FORMAT_TASKS else "internal"


def rate(root: Path, model: str, task: str) -> float | None:
    recs = records(root, model, task)
    # computed and formatted exactly like the report tables (paired_compare: (k / n) * 100, then :.1f), so
    # values on a rounding boundary such as 28.75 come out the same in both
    return float(f"{sum(OUTCOME[task](r) for r in recs.values()) / len(recs) * 100:.1f}") if recs else None


def paired(a: tuple[Path, str], b: tuple[Path, str], task: str) -> dict | None:
    row = compare_tasks(a[0], a[1], task, b[0], b[1], task)
    return None if row is None else {"n": row["n"], "only_a": row["only_a"], "only_b": row["only_b"],
                                     "p": round(row["p"], 6)}


def summary(root: Path, model: str, task: str) -> dict:
    runs = [d for d in (root / task).glob(f"{model}__*") if d.is_dir()]
    return json.loads((runs[0] / "summary.json").read_text()) if runs else {}


def baselines() -> dict:
    systems = [("Qwen2.5-Coder-1.5B", R / "kaggle_baselines_20261012/results", "qwen2.5-coder-1.5b"),
               ("Phi-4-mini (3.8B)", R / "kaggle_baselines_20261012/results", "phi-4-mini"),
               ("Qwen3.5-2B", R / "kaggle_baselines_20261012/results", "qwen3.5-2b"),
               ("Qwen3.5-4B", R / "kaggle_baselines_20261012/results", "qwen3.5-4b"),
               ("Qwen3.5-9B (reference)", R / "kaggle_reference_20261012/results", "qwen3.5-9b")]
    rows = []
    for task in BENCHMARKS:
        row = {"task": task, "label": LABELS[task], "systems": {}}
        for label, root, model in systems:
            s = summary(root, model, task)
            row["systems"][label] = {"score": rate(root, model, task),
                                     "gpu_j_per_item": (s.get("gpu_energy") or {}).get("j_per_task"),
                                     "output_tokens": s.get("metrics", {}).get("mean_output_tokens")}
        rows.append(row)
    return {"note": "Kaggle T4, vLLM FP16, greedy decoding; the 9B model ran on two T4s.",
            "systems": [s[0] for s in systems], "rows": rows}


def finetuning() -> dict:
    rows = []
    for task in BENCHMARKS + FORMAT_TASKS + INTERNAL:
        f = family(task)
        base, v1 = BASE[f], V1[f]
        row = {"task": task, "label": LABELS[task], "family": f,
               "base": rate(*base, task), "v1": rate(*v1, task),
               "qlora_v2": rate(*V2["qlora"], task), "lora16_v2": rate(*V2["lora16"], task),
               "rslora_v2": rate(*V2["rslora"], task),
               "phi_base": rate(*PHI_BASE[f], task), "phi_qlora_v2": rate(*PHI_V2, task),
               "tests": {"base_vs_qlora_v2": paired(base, V2["qlora"], task),
                         "v1_vs_qlora_v2": paired(v1, V2["qlora"], task),
                         "phi_base_vs_phi_v2": paired(PHI_BASE[f], PHI_V2, task)}}
        rows.append(row)
    return {"note": "Paired on the same items; p is the exact two-sided McNemar test. Qwen2.5-Coder-1.5B "
                    "unless named; v1 and v2 are the two training mixtures.", "rows": rows}


def ladder() -> dict:
    lad, base_dir = R / "ladder_laptop", R / "baselines"
    configs = [("base", "F16", lad, "qwen2.5-coder-1.5b__f16"), ("base", "Q4_K_M", base_dir, "qwen2.5-coder-1.5b__q4km"),
               ("fine-tuned", "F16", lad, "qwen2.5-coder-1.5b-ft-qlora-v2__f16"),
               ("fine-tuned", "Q8_0", lad, "qwen2.5-coder-1.5b-ft-qlora-v2__q80"),
               ("fine-tuned", "Q4_K_M", lad, "qwen2.5-coder-1.5b-ft-qlora-v2__q4km")]
    memory = {}  # decimal GB, like the report
    with open(lad / "server_memory.tsv") as f:  # whole runs; only night 2 ran with the prompt cache off
        for time, model, quant, kb, _ in csv.reader(f, delimiter="\t"):
            if time >= "2026-10-14T07":
                memory[("base" if model == "qwen2.5-coder-1.5b" else "fine-tuned", quant)] = (round(int(kb) / 1e6, 2), "whole run")
    with open(lad / "memory_footprint.tsv") as f:  # load + one request, mmap and prompt cache off
        for row in csv.DictReader(f, delimiter="\t"):
            key = ("base" if row["model"] == "qwen2.5-coder-1.5b" else "fine-tuned", row["quant"])
            memory[key] = (round(int(row["peak_rss_kb"]) / 1e6, 2), "load + one request")
    rows = []
    for model, quant, root, prefix in configs:
        ram, ram_source = memory.get((model, quant), (None, None))
        entry = {"model": model, "quant": quant, "peak_ram_gb": ram, "peak_ram_source": ram_source, "tasks": {}}
        for task in ("humaneval_plus", "mbpp_plus", "humanevalfix"):
            runs = sorted((root / task).glob(f"{prefix}__laptop-cpu*"))
            if not runs:
                continue
            m = json.loads((runs[-1] / "summary.json").read_text())["metrics"]
            recs = [json.loads(line) for line in (runs[-1] / "samples.jsonl").read_text().splitlines()]
            solved = sum(r["passed"] for r in recs)
            entry["tasks"][task] = {"score": round(100 * solved / len(recs), 1), "tokens_per_s": m["mean_decode_tok_per_s"],
                                    "j_per_item": m["mean_energy_j_per_task"],
                                    "j_per_solved": round(m["total_energy_j"] / solved) if solved else None,
                                    "output_tokens": m["mean_output_tokens"]}
        rows.append(entry)
    return {"note": "Laptop CPU (i5-10210U, 4 threads), llama.cpp, greedy; energy is the CPU package (RAPL).",
            "rows": rows}


def context_ablation() -> dict:
    root, model = R / "context_ablation_t4/results", "qwen2.5-coder-1.5b-ft-qlora-v2-merged"
    rows = []
    for task, label in [("internal_t1", "Failing test only (trained prompt)"), ("internal_t1_fullctx", "Whole test suite"),
                        ("internal_t1_compressed", "Compressed (no comments, docstrings)")]:
        s = summary(root, model, task)
        rows.append({"variant": label, "score": rate(root, model, task),
                     "input_tokens": s["metrics"]["mean_input_tokens"], "output_tokens": s["metrics"]["mean_output_tokens"],
                     "gpu_j": (s.get("gpu_energy") or {}).get("total_j"),
                     "vs_standard": None if task == "internal_t1" else _vs_standard(root, model, task)})
    return {"note": "212 held-out repair problems, merged QLoRA v2 model on a T4.", "rows": rows}


def _vs_standard(root: Path, model: str, task: str) -> dict:
    row = compare_tasks(root, model, "internal_t1", root, model, task)
    return {"only_standard": row["only_a"], "only_variant": row["only_b"], "p": round(row["p"], 6)}


def agents() -> dict:
    runs = [("Single agent", "det-single"), ("Multi-agent, no tools", "det-multi-notools"),
            ("Multi-agent + tools", "det-multi-a"), ("Multi-agent + tools, per-change patches", "det-multi-split")]
    rows = []
    for label, folder in runs:
        path = R / "agents_demo_repo" / folder / "score.json"
        if path.exists():
            s = json.loads(path.read_text())
            rows.append({"variant": label, "bugs": s["bugs"], "security": s["security"], "secrets": s["secrets"],
                         "false_positives": sum(s["false_positives"].values()), "model_calls": s["model_calls"],
                         "output_tokens": s["output_tokens"]})
    return {"note": "demo_repo with 5 planted bugs, 5 vulnerabilities and hardcoded secrets; fine-tuned Q8_0 on the "
                    "laptop. 'restock boundary' counts as suspected only through a wrong generated test.", "rows": rows}


def main() -> None:
    out = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "baselines": baselines(),
           "finetuning": finetuning(), "ladder": ladder(), "context_ablation": context_ablation(), "agents": agents()}
    (R / "summary.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {R / 'summary.json'}")


if __name__ == "__main__":
    main()
