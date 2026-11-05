"""Charts for the README report (docs/figures/*.svg), computed from the committed result folders.

    uv run python experiments/scripts/report_figures.py
"""

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "experiments" / "results"
OUT = ROOT / "docs" / "figures"

BASE, FT = "#2a78d6", "#eb6834"  # validated categorical pair (colour-blind safe)
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

mpl.rcParams.update({
    "font.family": "sans-serif", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "svg.fonttype": "none", "svg.hashsalt": "locali",
})


def share(path: Path, key: str = "passed") -> float:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return 100 * sum(bool(r[key]) for r in rows) / len(rows)


def run(root: str, task: str, model: str) -> Path:
    return next((RES / root / "results" / task).glob(f"{model}__*")) / "samples.jsonl"


def fine_tuning() -> None:
    base, d = "qwen2.5-coder-3b", "qwen2.5-coder-3b-ft-qlora-mixv3b-diag"
    rows = [  # label, base, run D, verdict
        ("Fix bugs: benchmark (HumanEvalFix)", share(run("kaggle_coder_baselines_20261024", "humanevalfix", base)),
         share(run("finetune_qwen25_3b_qlora_mixv3b_diag", "humanevalfix", d)), "better"),
        ("Fix bugs: real bugs (ConDefects)", share(RES / "repair_prereg_t4/results/condefects" / base / "samples.jsonl"),
         share(RES / "repair_prereg_t4/results/condefects" / d / "samples.jsonl"), "not proven"),
        ("Write tests: bugs caught", share(RES / "testgen2048_t4/results" / base / "samples.jsonl", "caught_bug"),
         share(RES / "testgen2048_t4/results" / d / "samples.jsonl", "caught_bug"), "better"),
        ("Write code (HumanEval+)", share(run("kaggle_coder_baselines_20261024", "humaneval_plus", base)),
         share(run("finetune_qwen25_3b_qlora_mixv3b_diag", "humaneval_plus", d)), "lower, not proven"),
        ("Explain code (HumanEvalExplain)", share(RES / "explain_t4/writer_3b" / base / "samples.jsonl"),
         share(RES / "explain_t4/writer_3b" / d / "samples.jsonl"), "same"),
    ]
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    height, gap = 0.36, 0.04
    for i, (label, b, f, verdict) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.barh(y + (height + gap) / 2, b, height, color=BASE)
        ax.barh(y - (height + gap) / 2, f, height, color=FT)
        ax.text(b + 1, y + (height + gap) / 2, f"{b:.0f} %", va="center", fontsize=9, color=INK)
        ax.text(f + 1, y - (height + gap) / 2, f"{f:.0f} %", va="center", fontsize=9, color=INK)
        ax.text(101, y, verdict, va="center", fontsize=9, color=MUTED, style="italic")
    ax.set_yticks(range(len(rows)), [r[0] for r in reversed(rows)])
    ax.set_xlim(0, 125)
    ax.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100 %"])
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.legend(handles=[mpl.patches.Patch(color=BASE, label="3B base"), mpl.patches.Patch(color=FT, label="Fine-tuned 3B (run D)")],
              loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "fine_tuning.svg", metadata={"Date": None})
    plt.close(fig)


def quantization() -> None:
    ladder = [  # from experiments/results/ladder_laptop/README.md (fine-tuned 1.5B, laptop CPU)
        ("F16", 3.21, 5.8, 64.4), ("Q8_0", 1.79, 10.4, 63.2), ("Q4_K_M", 1.16, 16.1, 60.1)]
    panels = [("Memory (GB)", 1, "{:.1f}"), ("Speed (words/s)", 2, "{:.1f}"), ("Correct code, HumanEval+ (%)", 3, "{:.0f}")]
    fig, axes = plt.subplots(1, 3, figsize=(8.2, 2.6))
    for ax, (title, col, fmt) in zip(axes, panels, strict=True):
        values = [row[col] for row in ladder]
        ax.bar(range(3), values, 0.6, color=BASE)
        for x, v in enumerate(values):
            ax.text(x, v * 1.02, fmt.format(v), ha="center", va="bottom", fontsize=9, color=INK)
        ax.set_xticks(range(3), [row[0] for row in ladder])
        ax.set_yticks([])
        ax.set_ylim(0, max(values) * 1.2)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.tick_params(axis="x", length=0)
        ax.spines["bottom"].set_color(GRID)
    fig.tight_layout()
    fig.savefig(OUT / "quantization.svg", metadata={"Date": None})
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fine_tuning()
    quantization()
    print("written:", sorted(p.name for p in OUT.glob("*.svg")))
