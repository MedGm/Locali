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
D_COLOUR = "#1baf7a"  # run D: categorical slot 3 (aqua); validated with the pair above, labels on every bar
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


BASE3 = "qwen2.5-coder-3b"
RUN_D, RUN_E = "qwen2.5-coder-3b-ft-qlora-mixv3b-diag", "qwen2.5-coder-3b-ft-qlora-mixv3s"
ROOTS = {BASE3: "kaggle_coder_baselines_20261024", RUN_D: "finetune_qwen25_3b_qlora_mixv3b_diag",
         RUN_E: "finetune_qwen25_3b_qlora_mixv3s"}
MODELS = [(BASE3, "Qwen2.5-Coder-3B (base)", BASE), (RUN_D, "Locali run D (earlier default)", D_COLOUR),
          (RUN_E, "Locali run E (default)", FT)]


def benchmark_rows() -> list[dict]:
    """Base 3B, run D and run E on each benchmark; p is run E (the default) vs the base, as the README uses it."""
    from multiple_comparisons import CONFIRMATORY, PAIRS, explain_row, holm
    from paired_compare import OUTCOME, compare_tasks, mcnemar_exact

    # exploratory family of run E, Holm-corrected exactly as in experiments/results/multiple_comparisons
    root_a, model_a, root_b, model_b = PAIRS["3B run E (default)"]
    family = [r for task in OUTCOME if task not in CONFIRMATORY and (r := compare_tasks(root_a, model_a, task, root_b, model_b, task))]
    family.append(explain_row(BASE3, RUN_E))
    corrected = dict(zip([r["task"] for r in family], holm([r["p"] for r in family]), strict=True))

    def scores(load) -> tuple[dict, float]:
        a, d, e = (load(m) for m in (BASE3, RUN_D, RUN_E))
        only_a, only_e = sum(a[i] and not e[i] for i in a), sum(e[i] and not a[i] for i in a)
        values = {m: 100 * sum(o.values()) / len(o) for m, o in ((BASE3, a), (RUN_D, d), (RUN_E, e))}
        return {"values": values, "n": len(a)}, mcnemar_exact(only_a, only_e)

    def std(task: str, key: str = "passed"):
        return scores(lambda m: outcomes(run(ROOTS[m], task, m), key))

    rows = []
    # the two claims and the pre-registered checks: uncorrected within their own (small) family
    fix, p = std("humanevalfix")
    _, p_tests = std("testgen", "caught_bug")  # the other confirmatory outcome (768 tokens), for Holm over the two
    rows.append({"name": "Fix bugs\nHumanEvalFix", **fix, "p": holm([p, p_tests])[0]})
    real, p = scores(lambda m: outcomes(RES / "repair_prereg_t4/results/condefects" / m / "samples.jsonl"))
    rows.append({"name": "Fix real bugs\nConDefects", **real, "p": p})
    tests, p = scores(lambda m: outcomes(RES / "testgen2048_t4/results" / m / "samples.jsonl", "caught_bug"))
    rows.append({"name": "Write tests\n(bugs caught)", **tests, "p": p})
    for task, name in (("humaneval_plus", "Write code\nHumanEval+"), ("mbpp_plus", "Write code\nMBPP+"),
                       ("cruxeval_o", "Predict output\nCRUXEval-O")):
        row, _ = std(task)
        rows.append({"name": name, **row, "p": corrected[task]})
    explain, _ = scores(lambda m: outcomes(RES / "explain_t4/results" / m / "samples.jsonl"))
    rows.append({"name": "Explain code\nHumanEvalExplain", **explain, "p": corrected["humanevalexplain"]})
    return rows


def verdict(row: dict) -> str:
    if row["p"] >= 0.05:
        return f"no clear difference\np = {row['p']:.2g}"
    better = row["values"][RUN_E] > row["values"][BASE3]
    return ("better" if better else "worse") + f"\np = {row['p']:.1g}"


def fine_tuning() -> None:
    rows = benchmark_rows()
    fig, ax = plt.subplots(figsize=(11, 5.4))
    width = 0.26
    for x, row in enumerate(rows):
        for k, (model, _, colour) in enumerate(MODELS):
            value = row["values"][model]
            offset = (k - 1) * (width + 0.02)
            ax.bar(x + offset, value, width, color=colour)
            ax.text(x + offset, value + 1.2, f"{value:.0f}", ha="center", va="bottom", fontsize=8.5, color=INK,
                    weight="bold" if model == RUN_E else "normal")
        significant = row["p"] < 0.05
        ax.text(x, 104, verdict(row), ha="center", va="bottom", fontsize=8.5, linespacing=1.3,
                color=INK if significant else MUTED, weight="bold" if significant else "normal")
    for x in range(len(rows) - 1):
        ax.axvline(x + 0.5, color=GRID, linewidth=0.8, zorder=0)
    ax.axvline(2.5, color=MUTED, linewidth=1.0, linestyle=(0, (3, 3)), zorder=0)
    ax.text(1.0, -24, "what the training was for", ha="center", fontsize=9, color=MUTED, style="italic")
    ax.text(4.5, -24, "general skills (stricter bar: Holm correction)", ha="center", fontsize=9, color=MUTED, style="italic")
    ax.text(len(rows) - 0.4, 116, "verdict: run E vs base", ha="right", fontsize=8, color=MUTED, style="italic")
    ax.set_xticks(range(len(rows)), [f"{r['name']}\n({r['n']} problems)" for r in rows], fontsize=9.5)
    ax.tick_params(axis="x", length=0)
    ax.set_ylim(0, 118)
    ax.set_xlim(-0.6, len(rows) - 0.4)
    ax.set_yticks([0, 20, 40, 60, 80, 100], ["0", "20", "40", "60", "80", "100 %"])
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_axisbelow(True)
    ax.legend(handles=[mpl.patches.Patch(color=c, label=label) for _, label, c in MODELS],
              loc="lower center", bbox_to_anchor=(0.5, 1.07), ncol=3, frameon=False, fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "fine_tuning.svg", metadata={"Date": None})
    plt.close(fig)
    for row in rows:
        v = row["values"]
        print(f"{row['name'].replace(chr(10), ' '):34} n={row['n']:3}  base {v[BASE3]:5.1f}  D {v[RUN_D]:5.1f}  "
              f"E {v[RUN_E]:5.1f}  p(E vs base) {row['p']:.2g}")


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
