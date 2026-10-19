"""Figures for the paper (paper/fig_*.pdf), computed from the committed result folders.

    uv run python experiments/scripts/paper_figures.py
"""

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "experiments" / "results"
OUT = ROOT / "paper"

PLAIN, NGRAM = "#2a78d6", "#eb6834"  # categorical slots 1 and 2 (validated for colour-blind readers)
BASE, FT = "#2a78d6", "#eb6834"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

mpl.rcParams.update({
    "font.family": "serif", "font.size": 8.5, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "pdf.fonttype": 42,
})


def joules_per_correct(run: Path) -> float:
    metrics = json.loads((run / "summary.json").read_text())["metrics"]
    passed = sum(json.loads(line)["passed"] for line in (run / "samples.jsonl").read_text().splitlines())
    return metrics["total_energy_j"] / passed


def one(pattern: str) -> Path:
    found = sorted(RES.glob(pattern))
    assert len(found) == 1, (pattern, found)
    return found[0]


def cpu_figure() -> None:
    ladder, spec = "ladder_laptop/{b}/", "speculative_laptop/{b}/"
    rows = [  # label, kind, folder pattern
        ("Base, F16", "plain", ladder + "qwen2.5-coder-1.5b__f16__*"),
        ("Fine-tuned, F16", "plain", ladder + "qwen2.5-coder-1.5b-ft-qlora-v2__f16__*"),
        ("Fine-tuned, Q8", "plain", spec + "*__q80-none__*"),
        ("Fine-tuned, Q8 + n-gram", "ngram", spec + "*__q80-ngram-simple__*"),
        ("Fine-tuned, Q4", "plain", spec + "*__q4km-none__*"),
        ("Fine-tuned, Q4 + n-gram", "ngram", spec + "*__q4km-ngram-simple__*"),
    ]
    benches = [("humaneval_plus", "HumanEval+ (163 problems)"), ("humanevalfix", "HumanEvalFix (164 bugs)")]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.4), sharey=True)
    axes[0].invert_yaxis()  # shared axis: inverting once flips both panels
    for ax, (bench, title) in zip(axes, benches, strict=True):
        values = []
        for label, kind, pattern in rows:
            found = sorted(RES.glob(pattern.format(b=bench)))
            values.append((label, kind, joules_per_correct(found[0]) if found else None))
        top = max(v for _, _, v in values if v)
        for y, (label, kind, v) in enumerate(values):
            if v is None:
                ax.text(4, y, "not run", va="center", fontsize=7.5, color=MUTED, style="italic")
                continue
            ax.barh(y, v, height=0.62, color=PLAIN if kind == "plain" else NGRAM,
                    hatch="////" if kind == "ngram" else None, edgecolor="white", linewidth=0.6)
            ax.text(v + top * 0.015, y, f"{v:.0f}", va="center", fontsize=7.5, color=INK)
        ax.set_yticks(range(len(rows)), [r[0] for r in rows])
        ax.set_xlim(0, top * 1.15)
        ax.set_title(title, fontsize=8.5, color=INK, loc="left")
        ax.set_xlabel("CPU energy per correct answer (J)")
        ax.grid(axis="x", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
    handles = [mpl.patches.Patch(color=PLAIN, label="plain decoding"),
               mpl.patches.Patch(facecolor=NGRAM, hatch="////", edgecolor="white", label="n-gram lookup")]
    fig.legend(handles=handles, frameon=False, loc="upper right", ncols=2, fontsize=7.5)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(OUT / "fig_cpu_energy.pdf")
    plt.close(fig)


def acceptance_figure() -> None:
    rows = json.loads((RES / "speculative_t4" / "runs.json").read_text())
    lengths = [2, 4, 8]
    benches = [("humaneval_plus", "HumanEval+"), ("humanevalfix", "HumanEvalFix")]
    fig, axes = plt.subplots(1, 2, figsize=(4.6, 2.0), sharey=True)
    for ax, (bench, title) in zip(axes, benches, strict=True):
        for target, colour, marker, name in (("base", BASE, "o", "base target"), ("ft", FT, "s", "fine-tuned target")):
            acc = [next(r["acceptance"] for r in rows if r["target"] == target and r["benchmark"] == bench
                        and r["workers"] == 1 and r["setting"] == f"draft-n{n}") for n in lengths]
            ax.plot(lengths, acc, color=colour, marker=marker, markersize=4.5, linewidth=1.6, label=name,
                    markeredgecolor="white", markeredgewidth=0.8)
            ax.text(8.25, acc[-1], f"{acc[-1]:.2f}", va="center", fontsize=7.5, color=INK)
        ax.set_xticks(lengths)
        ax.set_xlim(1.5, 9.2)
        ax.set_ylim(0.55, 1.0)
        ax.set_title(title, fontsize=8.5, color=INK, loc="left")
        ax.set_xlabel("drafted tokens")
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("draft acceptance")
    axes[0].legend(frameon=False, loc="lower left", fontsize=7.5)
    fig.tight_layout()
    fig.savefig(OUT / "fig_acceptance.pdf")
    plt.close(fig)


if __name__ == "__main__":
    cpu_figure()
    acceptance_figure()
    print("wrote", OUT / "fig_cpu_energy.pdf", OUT / "fig_acceptance.pdf")
