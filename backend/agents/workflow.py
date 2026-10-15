"""The assistant's workflow on one repository, as a LangGraph graph with fixed routing.

    prepare -> analyze -> review -> testgen -> debug -> propose -> report

Routing is fixed rather than chosen by the model: the 1.5B model made no native tool calls in the
W1 spike, and fixed steps make every run reproducible. All edits happen in an isolated workspace,
and the run ends with at most one validated patch waiting for approval (backend.patches). The
workspace is removed when the run ends, also on errors.
"""

from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agents.debug import debug_failing_tests
from backend.agents.review import review_functions
from backend.agents.testgen import generate_tests
from backend.analysis import analyze
from backend.patches import PatchStore, propose
from backend.validation import validate_workspace
from backend.workspace import Workspace, open_workspace
from security.secrets import redact

STEPS = ["prepare", "analyze", "review", "testgen", "debug", "propose", "report"]


class RunState(TypedDict, total=False):
    repo: str
    run_id: str
    workspace: str
    steps: list[str]
    findings: list[dict]
    review_dropped: int
    tests_added: list[str]
    suspects: list[dict]
    crashed_tests: dict[str, int]
    fixes: list[dict]
    patch_id: str | None
    validation: dict | None
    report: str


def _report(state: RunState) -> str:
    by_category = Counter(f["category"] for f in state["findings"])
    lines = [f"# Run {state['run_id']}", "", "## Findings", ""]
    lines += [f"- {cat}: {n}" for cat, n in sorted(by_category.items())] or ["- none"]
    lines += ["", f"Model review findings whose quoted line did not exist (dropped): {state['review_dropped']}"]
    lines += ["", "## Tests added", ""] + ([f"- {t}" for t in state["tests_added"]] or ["- none"])
    lines += ["", "## Suspected bugs (generated tests that failed; check the test before the code)", ""]
    lines += [f"- {s['file']}::{s['function']}: {s['error'].splitlines()[0]}" for s in state["suspects"]] or ["- none"]
    lines += ["", "## Fixes", ""]
    lines += [f"- {f['test']}: {'fixed' if f['fixed'] else 'not fixed'} in {f['attempts']} attempt(s), "
              f"{f['file']}::{f['function']}" for f in state["fixes"]] or ["- none"]
    lines += ["", "## Patch", ""]
    if state["patch_id"]:
        v = state["validation"]
        lines.append(f"- {state['patch_id']}: validation {'passed' if v['ok'] else 'FAILED'}, awaiting review")
    else:
        lines.append("- no changes")
    return redact("\n".join(lines) + "\n")


def build_workflow(model, store: PatchStore, workspaces: dict[str, Workspace], tools: bool = True,
                   on_step=None):
    """tools=False drops the static-analysis step (ablation); patch validation still uses the tools."""
    def step(name, update):
        def node(state: RunState) -> RunState:
            if on_step:
                on_step(name)
            return {**update(state), "steps": [*state.get("steps", []), name]}
        return node

    def prepare(state):
        ws = open_workspace(state["repo"])
        workspaces[state["run_id"]] = ws
        return {"workspace": str(ws.path)}

    def ws_of(state) -> Path:
        return Path(state["workspace"])

    def do_analyze(state):
        return {"findings": [{**asdict(f), "message": redact(f.message)} for f in analyze(ws_of(state))]}

    def do_review(state):
        result = review_functions(ws_of(state), model)
        return {"findings": state.get("findings", []) + result.findings, "review_dropped": result.dropped}

    def do_testgen(state):
        result = generate_tests(ws_of(state), model)
        return {"tests_added": result.files, "suspects": [asdict(s) for s in result.suspects],
                "crashed_tests": result.crashed}

    def do_debug(state):
        return {"fixes": [asdict(f) for f in debug_failing_tests(ws_of(state), model)]}

    def do_propose(state):
        ws = workspaces[state["run_id"]]
        diff = ws.diff()
        patch = propose(ws, run_id=state["run_id"], store=store,
                        validate=lambda path, files: validate_workspace(path, files, original=ws.repo, diff=diff))
        return {"patch_id": patch.id if patch else None, "validation": patch.validation if patch else None}

    def do_report(state):
        return {"report": _report(state)}

    graph = StateGraph(RunState)
    nodes = dict(zip(STEPS, [prepare, do_analyze, do_review, do_testgen, do_debug, do_propose, do_report], strict=True))
    steps = [s for s in STEPS if tools or s != "analyze"]
    for name in steps:
        graph.add_node(name, step(name, nodes[name]))
    for a, b in zip([START, *steps], [*steps, END], strict=True):
        graph.add_edge(a, b)
    return graph.compile()


def run_workflow(repo: str | Path, run_id: str, model, store: PatchStore, tools: bool = True,
                 on_step=None) -> RunState:
    """on_step(name) is called before each step runs (progress reporting)."""
    workspaces: dict[str, Workspace] = {}
    try:
        graph = build_workflow(model, store, workspaces, tools, on_step)
        return graph.invoke({"repo": str(Path(repo).resolve()), "run_id": run_id})
    finally:
        for ws in workspaces.values():
            ws.cleanup()
