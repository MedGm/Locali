"""The assistant's workflow on one repository, as a LangGraph graph with fixed routing.

    prepare -> analyze -> review -> testgen -> debug -> propose -> report

Routing is fixed rather than chosen by the model: the 1.5B model made no native tool calls in the
W1 spike, and fixed steps make every run reproducible. All edits happen in an isolated workspace,
and the run ends with at most one validated patch waiting for approval (backend.patches). The
workspace is removed when the run ends, also on errors.

The run ends with one patch per change rather than one for everything: a patch per fixed source
file and a patch per generated test file. Each is applied on its own to a fresh workspace and
validated there, so a reviewer can accept the fix and reject a test (or the other way round), and
the approval covers exactly that change.
"""

from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agents.debug import debug_failing_tests
from backend.agents.review import review_functions
from backend.agents.testgen import generate_tests, untested_functions
from backend.analysis import analyze
from backend.patches import PatchConflict, PatchStore, _git_apply, _touched, propose
from backend.validation import validate_workspace
from backend.workspace import Workspace, open_workspace
from mcp_servers.tests_server import run_tests
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
    patch_ids: list[str]
    patches: list[dict]
    report: str


def change_groups(state: RunState, changed: list[str]) -> list[tuple[list[str], str, str]]:
    """(files, kind, title) for each patch: one per fixed source file, one per generated test file,
    and one for anything else that changed."""
    groups = []
    fixed: dict[str, list[str]] = {}
    for f in state.get("fixes", []):
        if f["fixed"]:
            fixed.setdefault(f["file"], []).append(f["function"])
    for file, functions in sorted(fixed.items()):
        groups.append(([file], "fix", f"Fix {', '.join(sorted(set(functions)))} in {file}"))
    for test_file in state.get("tests_added", []):
        function = Path(test_file).stem.removeprefix("test_locali_")
        groups.append(([test_file], "tests", f"Regression tests for {function} (they record what the code does now)"))
    covered = {f for files, _, _ in groups for f in files}
    rest = [f for f in changed if f not in covered]
    if rest:
        groups.append((rest, "change", "Other changes"))
    return groups


def flagged_functions(root: Path, findings: list[dict]) -> set[tuple[str, str]]:
    """(file, function) pairs that contain a security finding from a static tool."""
    import ast

    lines: dict[str, set[int]] = {}
    for f in findings:
        if f["category"] == "security" and f["tool"] != "model" and f["path"].endswith(".py"):
            lines.setdefault(f["path"], set()).add(f["line"])
    flagged = set()
    for rel, hits in lines.items():
        for node in ast.parse((root / rel).read_text()).body:
            if isinstance(node, ast.FunctionDef) and any(node.lineno <= n <= node.end_lineno for n in hits):
                flagged.add((rel, node.name))
    return flagged


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
    lines += ["", "## Patches (each one is reviewed and applied on its own)", ""]
    lines += [f"- {p['id']} [{p['kind']}] {p['title']}: validation {'passed' if p['ok'] else 'FAILED'}"
              for p in state["patches"]] or ["- no changes"]
    return redact("\n".join(lines) + "\n")


def build_workflow(model, store: PatchStore, workspaces: dict[str, Workspace], tools: bool = True,
                   on_step=None, around_step=None):
    """tools=False drops the static-analysis step (ablation); patch validation still uses the tools."""
    def step(name, update):
        def node(state: RunState) -> RunState:
            if on_step:
                on_step(name, state)
            result = around_step(name, lambda: update(state)) if around_step else update(state)
            return {**result, "steps": [*state.get("steps", []), name]}
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
        # No regression tests for functions the tools flag as insecure: a test that passes today would
        # assert that the vulnerable behaviour is correct and get in the way of fixing it.
        flagged = flagged_functions(ws_of(state), state.get("findings", []))
        targets = [fn for fn in untested_functions(ws_of(state)) if fn not in flagged]
        result = generate_tests(ws_of(state), model, targets)
        return {"tests_added": result.files, "suspects": [asdict(s) for s in result.suspects],
                "crashed_tests": result.crashed}

    def do_debug(state):
        return {"fixes": [asdict(f) for f in debug_failing_tests(ws_of(state), model)]}

    def do_propose(state):
        ws = workspaces[state["run_id"]]
        failing_before = run_tests(ws.repo)["failed"]  # once per run, shared by every patch's validation
        made = []
        for paths, kind, title in change_groups(state, _touched(ws.diff())):
            diff = ws.diff(paths)
            fresh = open_workspace(ws.repo)
            try:
                if _git_apply(fresh.path, diff).returncode != 0:
                    raise PatchConflict(f"could not replay the change to {paths} on a fresh copy")
                patch = propose(fresh, run_id=state["run_id"], store=store, paths=paths, title=title, kind=kind,
                                validate=lambda path, files, d=diff: validate_workspace(
                                    path, files, original=ws.repo, diff=d, baseline_failed=failing_before))
            finally:
                fresh.cleanup()
            if patch:
                made.append({"id": patch.id, "kind": kind, "title": title, "files": patch.files,
                             "ok": bool(patch.validation.get("ok"))})
        return {"patch_ids": [p["id"] for p in made], "patches": made}

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
                 on_step=None, around_step=None) -> RunState:
    """on_step(name, state) is called before each step runs, with the results of the steps so far;
    around_step(name, run) wraps each step (tracing)."""
    workspaces: dict[str, Workspace] = {}
    try:
        graph = build_workflow(model, store, workspaces, tools, on_step, around_step)
        return graph.invoke({"repo": str(Path(repo).resolve()), "run_id": run_id})
    finally:
        for ws in workspaces.values():
            ws.cleanup()
