"""Run the full agent workflow on demo_repo with a real model and score it against the answer key.

    uv run python experiments/scripts/agent_eval.py --base-url http://127.0.0.1:8093/v1 \
        --out experiments/results/agents_demo_repo/<name>

Writes state.json (the run), score.json, report.md and one patch-<kind>-<id>.diff per patch to --out. demo_repo itself is
never modified: the workflow works in an isolated workspace and only proposes a patch.

--mode multi (default): the full workflow. multi-notools: the workflow without the static-analysis
step. single: one review call per file, no tools, tests or fixes (ablation baselines).
--context: how much code the review and test-generation steps show the model (file, function,
slice, compact; backend/agents/context.py). The API key, if the server needs one, is read from
LOCALI_MODEL_KEY.
"""

import argparse
import ast
import json
import os
import time
from collections import defaultdict
from pathlib import Path

from backend.agents.context import CONTEXTS
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
    parser.add_argument("--context", choices=CONTEXTS, default="function")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    client = ChatClient(args.base_url, model=args.model_name, api_key=os.environ.get("LOCALI_MODEL_KEY", "local"))
    calls = []
    current = {"step": None}

    def model(messages):
        c = client.complete(messages, max_tokens=768)
        calls.append({"step": current["step"], "input_tokens": c.input_tokens, "output_tokens": c.output_tokens,
                      "total_s": c.total_s})
        return c.text

    def on_step(name, state):
        current["step"] = name

    start = time.time()
    if args.mode == "single":
        result = review_files(DEMO, model)
        state = {"findings": result.findings, "review_dropped": result.dropped, "suspects": [], "fixes": [],
                 "report": f"single-agent review: {len(result.findings)} findings, {result.dropped} dropped\n"}
    else:
        state = run_workflow(DEMO, run_id=args.out.name, model=model, store=PatchStore(args.out / "data"),
                             tools=args.mode == "multi", on_step=on_step, context=args.context)
    wall = time.time() - start
    score = score_run(state, KEY, enclosing_functions(DEMO, KEY))
    score["mode"] = args.mode
    score["context"] = args.context
    score["wall_s"] = round(wall, 1)
    score["model_calls"] = len(calls)
    score["input_tokens"] = sum(c["input_tokens"] or 0 for c in calls)
    score["output_tokens"] = sum(c["output_tokens"] or 0 for c in calls)
    score["generation_s"] = round(sum(c["total_s"] or 0 for c in calls), 1)
    per_step: dict[str, dict] = defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "seconds": 0.0})
    for c in calls:
        step = per_step[c["step"] or "review"]
        step["calls"] += 1
        step["input_tokens"] += c["input_tokens"] or 0
        step["output_tokens"] += c["output_tokens"] or 0
        step["seconds"] = round(step["seconds"] + (c["total_s"] or 0), 1)
    score["per_step"] = dict(per_step)
    planted = {(f["file"], f["line"], f["kind"]) for f in KEY["flaws"] if f["kind"] in ("bug", "security")}
    score["model_hits"] = sorted({f"{f['path']}:{f['line']}" for f in state["findings"]
                                  if f["tool"] == "model" and (f["path"], f["line"], f["category"]) in planted})
    score["tests_kept"] = len(state.get("tests_added", []))
    score["crashed_tests"] = sum(state.get("crashed_tests", {}).values())

    (args.out / "state.json").write_text(json.dumps(state, indent=1))
    (args.out / "score.json").write_text(json.dumps(score, indent=1))
    (args.out / "report.md").write_text(state["report"])
    store = PatchStore(args.out / "data")
    for patch_id in state.get("patch_ids", []):
        patch = store.get(patch_id)
        (args.out / f"patch-{patch.kind}-{patch_id}.diff").write_text(patch.diff)
    print(json.dumps(score, indent=1))


if __name__ == "__main__":
    main()
