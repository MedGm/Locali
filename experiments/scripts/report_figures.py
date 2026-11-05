"""Charts for the README report (docs/figures/*.svg), computed from the committed result folders.

    uv run python experiments/scripts/report_figures.py
"""

import json
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "experiments" / "results"
OUT = ROOT / "docs" / "figures"
sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE, FT = "#2a78d6", "#eb6834"  # validated categorical pair (colour-blind safe)
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

mpl.rcParams.update({
    "font.family": "sans-serif", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "svg.fonttype": "none", "svg.hashsalt": "locali",
})


def outcomes(path: Path, key: str = "passed") -> dict[str, bool]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {r["task_id"]: bool(r[key]) for r in rows}


def run(root: str, task: str, model: str) -> Path:
    return next((RES / root / "results" / task).glob(f"{model}__*")) / "samples.jsonl"


BASE3, RUN_D = "qwen2.5-coder-3b", "qwen2.5-coder-3b-ft-qlora-mixv3b-diag"


def benchmark_rows() -> list[dict]:
    """Base 3B vs run D on each benchmark, with the p-value the README uses for that row."""
    from multiple_comparisons import CONFIRMATORY, PAIRS, explain_row, holm
    from paired_compare import OUTCOME, compare_tasks, mcnemar_exact

    # exploratory family of run D, Holm-corrected exactly as in experiments/results/multiple_comparisons
    root_a, model_a, root_b, model_b = PAIRS["3B run D (default)"]
    family = [r for task in OUTCOME if task not in CONFIRMATORY and (r := compare_tasks(root_a, model_a, task, root_b, model_b, task))]
    family.append(explain_row(BASE3, "qwen2.5-coder-3b-ft-qlora-mixv3b-diag"))
    corrected = dict(zip([r["task"] for r in family], holm([r["p"] for r in family]), strict=True))

    def pair(a: dict, b: dict) -> tuple[float, float, int, float]:
        only_a, only_b = sum(a[i] and not b[i] for i in a), sum(b[i] and not a[i] for i in a)
        return 100 * sum(a.values()) / len(a), 100 * sum(b.values()) / len(b), len(a), mcnemar_exact(only_a, only_b)

    base_root, d_root = "kaggle_coder_baselines_20261024", "finetune_qwen25_3b_qlora_mixv3b_diag"
    def std(task: str, key: str = "passed") -> tuple[float, float, int, float]:
        return pair(outcomes(run(base_root, task, BASE3), key), outcomes(run(d_root, task, RUN_D), key))
    rows = []
    # the two claims and the pre-registered checks: uncorrected within their own (small) family
    b, d, n, p = std("humanevalfix")
    _, _, _, p_tests = std("testgen", "caught_bug")  # the other confirmatory outcome (768 tokens), for Holm over the two
    p = holm([p, p_tests])[0]
    rows.append({"name": "Fix bugs\nHumanEvalFix", "base": b, "ft": d, "n": n, "p": p, "kind": "claim"})
    b, d, n, p = pair(*(outcomes(RES / "repair_prereg_t4/results/condefects" / m / "samples.jsonl") for m in (BASE3, RUN_D)))
    rows.append({"name": "Fix real bugs\nConDefects", "base": b, "ft": d, "n": n, "p": p, "kind": "check"})
    b, d, n, p = pair(*(outcomes(RES / "testgen2048_t4/results" / m / "samples.jsonl", "caught_bug") for m in (BASE3, RUN_D)))
    rows.append({"name": "Write tests\n(bugs caught)", "base": b, "ft": d, "n": n, "p": p, "kind": "check"})
    for task, name in (("humaneval_plus", "Write code\nHumanEval+"), ("mbpp_plus", "Write code\nMBPP+"),
                       ("cruxeval_o", "Predict output\nCRUXEval-O")):
        b, d, n, _ = std(task)
        rows.append({"name": name, "base": b, "ft": d, "n": n, "p": corrected[task], "kind": "exploratory"})
    explain = explain_row(BASE3, RUN_D)
    rows.append({"name": "Explain code\nHumanEvalExplain", "base": 100 * explain["a"], "ft": 100 * explain["b"],
                 "n": explain["n"], "p": corrected["humanevalexplain"], "kind": "exploratory"})
    return rows


def verdict(row: dict) -> str:
    if row["p"] >= 0.05:
        return f"no clear difference\np = {row['p']:.2g}"
    return ("better" if row["ft"] > row["base"] else "worse") + f"\np = {row['p']:.1g}"


def fine_tuning() -> None:
    rows = benchmark_rows()
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    width = 0.36
    for x, row in enumerate(rows):
        for offset, value, colour in ((-width / 2 - 0.02, row["base"], BASE), (width / 2 + 0.02, row["ft"], FT)):
            ax.bar(x + offset, value, width, color=colour)
            ax.text(x + offset, value + 1.2, f"{value:.1f}", ha="center", va="bottom", fontsize=9.5, color=INK,
                    weight="bold" if colour == FT else "normal")
        significant = row["p"] < 0.05
        ax.text(x, 104, verdict(row), ha="center", va="bottom", fontsize=8.5, linespacing=1.3,
                color=INK if significant else MUTED, weight="bold" if significant else "normal")
    for x in range(len(rows) - 1):
        ax.axvline(x + 0.5, color=GRID, linewidth=0.8, zorder=0)
    ax.axvline(2.5, color=MUTED, linewidth=1.0, linestyle=(0, (3, 3)), zorder=0)
    ax.text(1.0, -24, "what the training was for", ha="center", fontsize=9, color=MUTED, style="italic")
    ax.text(4.5, -24, "general skills (stricter bar: Holm correction)", ha="center", fontsize=9, color=MUTED, style="italic")
    ax.set_xticks(range(len(rows)), [f"{r['name']}\n({r['n']} problems)" for r in rows], fontsize=9.5)
    ax.tick_params(axis="x", length=0)
    ax.set_ylim(0, 118)
    ax.set_xlim(-0.6, len(rows) - 0.4)
    ax.set_yticks([0, 20, 40, 60, 80, 100], ["0", "20", "40", "60", "80", "100 %"])
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_axisbelow(True)
    ax.legend(handles=[mpl.patches.Patch(color=BASE, label="Qwen2.5-Coder-3B (base)"),
                       mpl.patches.Patch(color=FT, label="Locali fine-tune (run D)")],
              loc="lower center", bbox_to_anchor=(0.5, 1.07), ncol=2, frameon=False, fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "fine_tuning.svg", metadata={"Date": None})
    plt.close(fig)
    for row in rows:
        print(f"{row['name'].replace(chr(10), ' '):34} n={row['n']:3}  base {row['base']:5.1f}  run D {row['ft']:5.1f}  p {row['p']:.2g}")


def quantization() -> None:
    ladder = [  # from experiments/results/ladder_laptop/README.md (fine-tuned 1.5B, laptop CPU)
        ("16-bit", 3.21, 5.8, 64.4), ("8-bit", 1.79, 10.4, 63.2), ("4-bit", 1.16, 16.1, 60.1)]
    panels = [("Memory", "GB, lower is better", 1, "{:.1f}"), ("Speed", "words per second, higher is better", 2, "{:.1f}"),
              ("Correct code", "% of HumanEval+, higher is better", 3, "{:.1f}")]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.4), gridspec_kw={"wspace": 0.12})
    for ax, (title, unit, col, fmt) in zip(axes, panels, strict=True):
        values = [row[col] for row in ladder]
        ax.set_facecolor("#ffffff")
        for side in ("top", "right", "left", "bottom"):
            ax.spines[side].set_visible(True)
            ax.spines[side].set_color(GRID)
        ax.bar(range(3), values, 0.56, color=BASE)
        for x, v in enumerate(values):
            ax.text(x, v + max(values) * 0.03, fmt.format(v), ha="center", va="bottom", fontsize=10, color=INK)
        ax.set_xticks(range(3), [row[0] for row in ladder], fontsize=9.5)
        ax.set_yticks([])
        ax.set_ylim(0, max(values) * 1.3)
        ax.set_xlim(-0.6, 2.6)
        ax.set_title(f"{title}\n", fontsize=11, color=INK, weight="bold", loc="left")
        ax.text(0, 1.02, unit, transform=ax.transAxes, fontsize=8.5, color=MUTED)
        ax.tick_params(axis="x", length=0)
    fig.tight_layout()
    fig.savefig(OUT / "quantization.svg", metadata={"Date": None})
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fine_tuning()
    quantization()
    print("written:", sorted(p.name for p in OUT.glob("*.svg")))
