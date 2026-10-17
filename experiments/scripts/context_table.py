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


def main() -> None:
    scores = {}
    for path in RUNS.glob("*/score.json"):
        # rescored from the saved run, so every run is judged by the current scoring rules
        state = json.loads((path.parent / "state.json").read_text())
        scores[path.parent.name] = json.loads(path.read_text()) | score_run(state, KEY, enclosing_functions(DEMO, KEY))
    header = ("| Context | Review input tokens | Test-gen input tokens | All input tokens | Output tokens | "
              "Model time | Review hits on planted flaws | Model false positives | Bugs fixed / found / suspected | "
              "Tests kept / crashed |")
    lines = [header, "|---|---|---|---|---|---|---|---|---|---|"]
    for name in [c for c in ORDER if c in scores]:
        s = scores[name]
        steps = s["per_step"]
        bugs = list(s["bugs"].values())
        lines.append(
            f"| {name} | {steps.get('review', {}).get('input_tokens', 0):,} | "
            f"{steps.get('testgen', {}).get('input_tokens', 0):,} | {s['input_tokens']:,} | {s['output_tokens']:,} | "
            f"{s['generation_s'] / 60:.1f} min | {len(s['model_hits'])} | {s['false_positives'].get('model', 0)} | "
            f"{bugs.count('fixed')} / {bugs.count('found')} / {bugs.count('suspected')} | "
            f"{s['tests_kept']} / {s['crashed_tests']} |")
    table = "\n".join(lines) + "\n"
    (RUNS / "table.md").write_text(table)
    print(table)


if __name__ == "__main__":
    main()
