"""Table of the agent context runs (experiments/results/context_agents/<context>/score.json).

    uv run python experiments/scripts/context_table.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.agents.scoring import score_run
from experiments.scripts.agent_eval import DEMO, KEY, enclosing_functions

RUNS = ROOT / "experiments" / "results" / "context_agents"
ORDER = ["file", "function", "slice", "compact"]


def collect() -> list[dict]:
    """One row per context setting, rescored from the saved run with the current scoring rules."""
    scores = {}
    for path in RUNS.glob("*/score.json"):
        state = json.loads((path.parent / "state.json").read_text())
        scores[path.parent.name] = json.loads(path.read_text()) | score_run(state, KEY, enclosing_functions(DEMO, KEY))
    rows = []
    for name in [c for c in ORDER if c in scores]:
        s = scores[name]
        steps, bugs = s["per_step"], list(s["bugs"].values())
        rows.append({
            "context": name, "review_input": steps.get("review", {}).get("input_tokens", 0),
            "testgen_input": steps.get("testgen", {}).get("input_tokens", 0), "input_tokens": s["input_tokens"],
            "output_tokens": s["output_tokens"], "minutes": round(s["generation_s"] / 60, 1),
            "review_hits": len(s["model_hits"]), "model_false_positives": s["false_positives"].get("model", 0),
            "fixed": bugs.count("fixed"), "found": bugs.count("found"), "suspected": bugs.count("suspected"),
            "tests_kept": s["tests_kept"], "tests_crashed": s["crashed_tests"],
        })
    return rows


def main() -> None:
    header = ("| Context | Review input tokens | Test-gen input tokens | All input tokens | Output tokens | "
              "Model time | Review hits on planted flaws | Model false positives | Bugs fixed / found / suspected | "
              "Tests kept / crashed |")
    lines = [header, "|---|---|---|---|---|---|---|---|---|---|"]
    for r in collect():
        lines.append(
            f"| {r['context']} | {r['review_input']:,} | {r['testgen_input']:,} | {r['input_tokens']:,} | "
            f"{r['output_tokens']:,} | {r['minutes']:.1f} min | {r['review_hits']} | {r['model_false_positives']} | "
            f"{r['fixed']} / {r['found']} / {r['suspected']} | {r['tests_kept']} / {r['tests_crashed']} |")
    table = "\n".join(lines) + "\n"
    (RUNS / "table.md").write_text(table)
    print(table)


if __name__ == "__main__":
    main()
