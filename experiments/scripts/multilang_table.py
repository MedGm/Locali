"""Table of HumanEvalFix in other languages, base vs fine-tuned (training/kaggle/multilang).

    uv run python experiments/scripts/multilang_table.py [results folder ...]

Each results folder is an unzipped job output (validation.json, results/<model>/<lang>/samples.jsonl);
a later folder replaces the languages it holds (e.g. a Rust-only rerun). A problem counts only if
its reference solution passed the harness on Kaggle, so a broken harness case never counts against
either model. Writes table.md next to this run's results.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from paired_compare import mcnemar_exact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "experiments" / "results" / "multilang_t4"
NAMES = {"js": "JavaScript", "java": "Java", "go": "Go", "cpp": "C++", "rust": "Rust"}


def load(folders: list[Path]) -> dict[str, dict]:
    langs: dict[str, dict] = {}
    for folder in folders:
        validation = json.loads((folder / "validation.json").read_text())
        for lang, check in validation.items():
            bad = {task for task, *_ in check.get("canonical_failures", [])}
            runs = {}
            for model in ("base", "ft"):
                path = folder / "results" / model / lang / "samples.jsonl"
                if path.exists():
                    runs[model] = {r["task_id"]: r for r in map(json.loads, path.read_text().splitlines())}
            if len(runs) == 2:
                langs[lang] = {"excluded": bad, "check": check, **runs}
    return langs


def collect(folders: list[Path]) -> list[dict]:
    langs = load(folders)
    rows = []
    for lang in [lg for lg in NAMES if lg in langs]:
        d = langs[lang]
        ids = [t for t in d["base"] if t not in d["excluded"] and t in d["ft"]]
        base = [d["base"][t]["passed"] for t in ids]
        ft = [d["ft"][t]["passed"] for t in ids]
        b = sum(x and not y for x, y in zip(base, ft, strict=True))
        c = sum(y and not x for x, y in zip(base, ft, strict=True))
        rows.append({"language": NAMES[lang], "n": len(ids), "base": round(100 * sum(base) / len(ids), 1),
                     "ft": round(100 * sum(ft) / len(ids), 1),
                     "change": round(100 * (sum(ft) - sum(base)) / len(ids), 1), "only_base": b, "only_ft": c,
                     "p": float(f"{mcnemar_exact(b, c):.3g}"), "excluded": sorted(d["excluded"])})
    return rows


def main() -> None:
    folders = [Path(a) for a in sys.argv[1:]] or [DEFAULT]
    lines = [
        "| Language | Problems scored | Base | Fine-tuned | Change | Only base fixed / only fine-tuned fixed | p (exact McNemar) |",
        "|---|---|---|---|---|---|---|",
        "| Python (for reference, [finetune_v2](../finetune_v2/README.md)) | 164 | 25.0 | 36.0 | +11.0 | | 0.006 |",
    ]
    rows = collect(folders)
    for r in rows:
        lines.append(f"| {r['language']} | {r['n']} of 164 | {r['base']:.1f} | {r['ft']:.1f} | {r['change']:+.1f} | "
                     f"{r['only_base']} / {r['only_ft']} | {r['p']:.3g} |")
    out = folders[0] / "table.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    for r in rows:
        if r["excluded"]:
            print(f"\n{r['language']}: excluded {r['excluded']}")


if __name__ == "__main__":
    main()
