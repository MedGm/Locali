"""Run the full agent workflow on demo_repo with a real model and score it against the answer key.

    uv run python experiments/scripts/agent_eval.py --base-url http://127.0.0.1:8093/v1 \
        --out experiments/results/agents_demo_repo/<name>

Writes state.json (the run), score.json, report.md and patch.diff to --out. demo_repo itself is
never modified: the workflow works in an isolated workspace and only proposes a patch.

--mode multi (default): the full workflow. multi-notools: the workflow without the static-analysis
step. single: one review call per file, no tools, tests or fixes (ablation baselines).
"""

import argparse
import ast
import json
import time
from pathlib import Path

from backend.agents.scoring import score_run
from backend.agents.single import review_files
from backend.agents.workflow import run_workflow
from backend.patches import PatchStore
from evaluation.client import ChatClient

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo_repo"
KEY = json.loads((ROOT / "security" / "demo_repo_flaws.json").read_text())


def enclosing_functions(repo: Path, key: dict) -> dict[tuple[str, int], str]:
    out = {}
    for flaw in key["flaws"]:
        path = repo / flaw["file"]
        if path.suffix != ".py":
            continue
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.FunctionDef) and node.lineno <= flaw["line"] <= node.end_lineno:
                out[(flaw["file"], flaw["line"])] = node.name
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model-name", default="local")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=["multi", "multi-notools", "single"], default="multi")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    client = ChatClient(args.base_url, model=args.model_name)
    calls = []

    def model(messages):
        c = client.complete(messages, max_tokens=768)
        calls.append({"input_tokens": c.input_tokens, "output_tokens": c.output_tokens, "total_s": c.total_s})
        return c.text

    start = time.time()
    if args.mode == "single":
        result = review_files(DEMO, model)
        state = {"findings": result.findings, "review_dropped": result.dropped, "suspects": [], "fixes": [],
                 "report": f"single-agent review: {len(result.findings)} findings, {result.dropped} dropped\n"}
    else:
        state = run_workflow(DEMO, run_id=args.out.name, model=model, store=PatchStore(args.out / "data"),
                             tools=args.mode == "multi")
    wall = time.time() - start
    score = score_run(state, KEY, enclosing_functions(DEMO, KEY))
    score["mode"] = args.mode
    score["wall_s"] = round(wall, 1)
    score["model_calls"] = len(calls)
    score["output_tokens"] = sum(c["output_tokens"] or 0 for c in calls)

    (args.out / "state.json").write_text(json.dumps(state, indent=1))
    (args.out / "score.json").write_text(json.dumps(score, indent=1))
    (args.out / "report.md").write_text(state["report"])
    if state.get("patch_id"):
        (args.out / "patch.diff").write_text(PatchStore(args.out / "data").get(state["patch_id"]).diff)
    print(json.dumps(score, indent=1))


if __name__ == "__main__":
    main()
