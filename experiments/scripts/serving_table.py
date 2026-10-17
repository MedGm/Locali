"""Tables and plots of the C4 serving runs (training/kaggle/serving), after local scoring.

    for d in experiments/results/serving_t4/results/internal_t1/*/; do
        uv run python -m evaluation.rescore "$d"; done
    uv run python experiments/scripts/serving_table.py

Writes experiments/results/serving_t4/tables.md, throughput.png and latency.png.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments" / "results" / "serving_t4"
RUNS = OUT / "results" / "internal_t1"
# categorical slots 1-3 of the app's validated palette (frontend/src/app/globals.css), light mode
COLORS = {"prefix-on-eager": "#2a78d6", "prefix-off-eager": "#eb6834", "prefix-on-graphs": "#1baf7a"}
LABELS = {"prefix-on-eager": "prefix cache on, eager", "prefix-off-eager": "prefix cache off, eager",
          "prefix-on-graphs": "prefix cache on, CUDA graphs"}


def samples(run: str) -> dict[str, dict]:
    path = RUNS / run / "samples.jsonl"
    return {s["task_id"]: s for s in map(json.loads, path.read_text().splitlines())}


def vllm_table(rows: list[dict]) -> list[str]:
    reference = samples("prefix-on-eager__c1")
    header = ("| Server | Concurrent requests | Items | Wall time | Throughput | Mean TTFT | Mean request time | "
              "GPU energy per item | pass@1 | Same answer as reference |")
    lines = [header, "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        name = r["run"]
        summary = json.loads((RUNS / name / "summary.json").read_text())
        mine = samples(name)
        same = sum(mine[t]["completion"] == reference[t]["completion"] for t in mine if t in reference)
        pass1 = summary["metrics"].get("pass@1")
        label = LABELS[r["config"]] + (", warm (second pass)" if r.get("warm") else "")
        lines.append(f"| {label} | {r['workers']} | {r['items']} | {r['wall_s']:.0f} s | {r['throughput_tok_s']} tok/s | "
                     f"{r['mean_ttft_s']:.3f} s | {r['mean_total_s']:.2f} s | {r['gpu_energy_j'] / r['items']:.0f} J | "
                     f"{'—' if pass1 is None else f'{pass1 * 100:.1f}'} | {same}/{len(mine)} |")
    return lines


def usable(text: str) -> bool:
    """False for degenerate output such as one character repeated to the token limit."""
    return len(set(text.strip())) > 3


def hf_table(hf: dict, answers: dict[str, list[str]]) -> list[str]:
    header = ("| Run | Batch | Prompts | New tokens (max) | KV cache | Wall time | Tokens/s | Peak memory | "
              "Usable answers | Same answers as |")
    lines = [f"transformers {hf['transformers']}, torch {hf['torch']}, {hf['gpu']}, FP16, greedy.", "",
             header, "|---|---|---|---|---|---|---|---|---|---|"]
    for r in hf["rows"]:
        mine = answers[r["run"]]
        # the KV cache pair stops at 128 tokens, so it is compared with itself, not with the 256-token runs
        other = "sdpa__b1__cache-on__128" if r["run"].endswith("cache-off__128") else "sdpa__b1"
        same = "—" if r["run"] in (other, "sdpa__b1__cache-on__128") else \
            f"{sum(a == b for a, b in zip(mine, answers[other], strict=False))}/{len(mine)} ({other})"
        lines.append(f"| {r['run']} | {r['batch']} | {r['prompts']} | {r['max_new_tokens']} | "
                     f"{'on' if r['use_cache'] else 'off'} | {r['wall_s']:.1f} s | {r['tokens_per_s']} | "
                     f"{r['peak_memory_gb']} GB | {sum(map(usable, mine))}/{len(mine)} | {same} |")
    return lines


def plot(rows: list[dict], key: str, ylabel: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=150)
    for config, color in COLORS.items():
        pts = sorted((r["workers"], r[key]) for r in rows if r["config"] == config and not r.get("warm"))
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, linewidth=2, marker="o", markersize=8,
                    markeredgecolor="white", markeredgewidth=2, label=LABELS[config])
    ax.set_xscale("log", base=2)
    ax.set_xticks([1, 4, 16], labels=["1", "4", "16"])
    ax.set_xlabel("Concurrent requests", color="#52514e")
    ax.set_ylabel(ylabel, color="#52514e")
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", color="#e1e0d9", linewidth=1)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors="#898781")
    ax.legend(frameon=False, fontsize=8, labelcolor="#52514e")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    rows = json.loads((OUT / "vllm_runs.json").read_text())
    hf = json.loads((OUT / "hf_runs.json").read_text())
    answers = json.loads((OUT / "hf_answers.json").read_text())
    text = ["## vLLM on one T4", "", *vllm_table(rows), "", "## transformers on one T4", "", *hf_table(hf, answers)]
    (OUT / "tables.md").write_text("\n".join(text) + "\n")
    plot(rows, "throughput_tok_s", "Output tokens per second", OUT / "throughput.png")
    plot(rows, "mean_total_s", "Mean request time (s)", OUT / "latency.png")
    print("\n".join(text))


if __name__ == "__main__":
    main()
