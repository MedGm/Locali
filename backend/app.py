"""HTTP API of the assistant.

    uv run uvicorn backend.app:default_app --factory --reload

Only folders under LOCALI_REPOS_ROOT can be analysed. Every message leaving the backend goes
through secret redaction, and every action is appended to <data dir>/audit.jsonl.

Agent changes arrive as validated patches (backend.patches). A reviewer approves one exact patch
by sending back its SHA-256 and baseline; only then can it be applied, and it can be reverted.
A patch that went stale (the folder changed) is revalidated into a new proposal.

POST /runs with mode "agents" runs the agent workflow (backend.agents.workflow) in the background,
one run at a time, and returns at once; GET /runs/{id} shows queued -> running -> done | failed.
The model is the OpenAI-compatible endpoint in LOCALI_MODEL_URL (API key in LOCALI_MODEL_KEY);
without it, agent runs are refused.
"""

import asyncio
import hmac
import json
import os
import tempfile
import uuid
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, StringConstraints

from backend.agents.files import SKIP_DIRS, python_files
from backend.agents.model import guarded
from backend.agents.workflow import STEPS, run_workflow
from backend.analysis import analyze
from backend.audit import AuditLog
from backend.languages import count_languages
from backend.llmops import Tracker
from backend.patches import ApprovalMismatch, PatchConflict, PatchStore, StalePatch, propose
from backend.playground import build_messages
from backend.validation import validate_workspace
from backend.workspace import open_workspace
from security import commands, sandbox
from security.commands import run as run_command
from security.secrets import redact, secret_values

RESULTS_FILE = Path(__file__).resolve().parents[1] / "experiments" / "results" / "summary.json"
MODELS_FILE = Path(__file__).with_name("models.json")

# audit actions shown in the security center
SECURITY_ACTIONS = {"auth.refused", "run.refused", "command.refused", "model.redacted", "patch.stale",
                    "patch.conflict", "patch.revert_refused", "patch.rejected"}


# A model the playground can stream from: (messages, on_token) -> completion with text and counts
PlaygroundModel = Callable[[list[dict], Callable[[str], None]], Any]


class PlaygroundRequest(BaseModel):
    task: Literal["review", "tests", "fix", "explain", "free"]
    language: str = "python"
    code: Annotated[str, StringConstraints(max_length=20000)] = ""
    prompt: Annotated[str, StringConstraints(max_length=4000)] = ""
    test: Annotated[str, StringConstraints(max_length=10000)] = ""
    error: Annotated[str, StringConstraints(max_length=10000)] = ""
    model: str = "main"


class RunRequest(BaseModel):
    repo: str
    mode: Literal["analyze", "agents"] = "analyze"


Reviewer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class Approval(BaseModel):
    sha256: str
    baseline: dict[str, str | None]
    validation_sha256: str
    reviewer: Reviewer


class Rejection(BaseModel):
    reviewer: Reviewer


def run_metrics(state: dict, calls: list[dict]) -> dict:
    by_category = Counter(f["category"] for f in state["findings"])
    return {
        **{f"findings_{c}": by_category.get(c, 0) for c in ("bug", "security", "quality")},
        "suspects": len(state["suspects"]),
        "fixes_total": len(state["fixes"]),
        "fixes_fixed": sum(f["fixed"] for f in state["fixes"]),
        "tests_added": len(state["tests_added"]),
        "patches": len(state["patches"]),
        "patches_validated": sum(p["ok"] for p in state["patches"]),
        "model_calls": len(calls),
        "input_tokens": sum(c["input_tokens"] or 0 for c in calls),
        "output_tokens": sum(c["output_tokens"] or 0 for c in calls),
        "generation_s": round(sum(c["latency_s"] for c in calls), 1),
        "redactions": sum(c.get("redactions", 0) for c in calls),
    }


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _without_credentials(url: str | None) -> str | None:
    if not url:
        return url
    parts = urlsplit(url)
    host = parts.hostname or ""
    netloc = host + (f":{parts.port}" if parts.port else "")
    return urlunsplit(parts._replace(netloc=netloc))


def trend_point(run: dict) -> dict:
    findings = run.get("findings", [])
    counts = Counter(f["category"] for f in findings)
    tests = run.get("tests_before") or {}
    patches = run.get("patches", [])
    return {
        "id": run["id"], "created": run["created"], "mode": run["mode"],
        "findings": {c: counts.get(c, 0) for c in ("bug", "security", "quality")},
        "high_security": sum(f["category"] == "security" and f["severity"] == "high" for f in findings),
        "tests_passed": tests.get("passed"), "tests_failed": len(tests["failed"]) if "failed" in tests else None,
        "coverage_percent": tests.get("coverage_percent"),
        "patches": len(patches), "patches_validated": sum(bool(p.get("ok")) for p in patches),
        "ready_to_merge": (run.get("devops") or {}).get("ready_to_merge"),
    }


async def event_stream(load: Callable[[], dict], heartbeat_s: float, poll_s: float = 0.2):
    """Server-Sent Events for one run: its state whenever it changes, and a comment line when nothing has
    changed for heartbeat_s. A step can take minutes, and proxies drop a response that stays silent."""
    loop = asyncio.get_running_loop()
    last, quiet_since = None, loop.time()
    while True:
        run = load()
        view = {k: run.get(k) for k in ("id", "status", "step", "steps_done", "patch_ids", "error")}
        if view != last:
            yield f"data: {json.dumps(view)}\n\n"
            last, quiet_since = view, loop.time()
        elif loop.time() - quiet_since >= heartbeat_s:
            yield ": keepalive\n\n"
            quiet_since = loop.time()
        if run["status"] in ("done", "failed"):
            return
        await asyncio.sleep(poll_s)


def create_app(repos_root: str | Path, data_dir: str | Path,
               validate: Callable[[Path, list[str]], dict] | None = None,
               model: Callable[[list[dict]], str] | None = None, tools: bool = True,
               api_token: str | None = None, heartbeat_s: float = 15.0,
               results_file: str | Path | None = None, mlflow_uri: str | None = None,
               mlflow_artifacts: str | None = None,
               playground: dict[str, tuple[str, PlaygroundModel]] | None = None) -> FastAPI:
    """validate replaces the full workspace validation (tests use a stub); model answers chat messages
    for agent runs; tools=False drops the static-analysis step of agent runs (ablation); api_token,
    when set, is required as a Bearer token on every endpoint except /health; playground maps "main"
    (and optionally "compare") to (model id, streaming model) for the playground page."""
    playground = playground or {}
    repos_root = Path(repos_root).resolve()
    runs_dir = Path(data_dir) / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    audit = AuditLog(Path(data_dir) / "audit.jsonl")
    patches = PatchStore(Path(data_dir), audit)
    app = FastAPI(title="Locali")
    app.state.patches = patches
    app.state.agents = ThreadPoolExecutor(max_workers=1)  # model calls are CPU-heavy: one run at a time
    tracker = Tracker(mlflow_uri, mlflow_artifacts)
    app.state.tracker = tracker
    commands.REFUSAL_HOOKS.append(
        lambda cmd: audit.write("command.refused", program=redact(cmd[0]) if cmd else "", args=[redact(a) for a in cmd[1:3]]))

    @app.middleware("http")
    async def require_token(request: Request, call_next):
        if api_token and request.url.path != "/health":
            sent = request.headers.get("authorization", "")
            if not hmac.compare_digest(sent.encode(), f"Bearer {api_token}".encode()):
                audit.write("auth.refused", method=request.method, path=request.url.path)
                return JSONResponse(status_code=401, content={"detail": "missing or wrong API token"})
        return await call_next(request)

    def save_run(run: dict) -> None:
        fd, tmp = tempfile.mkstemp(dir=runs_dir, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(run))
        os.replace(tmp, runs_dir / f"{run['id']}.json")

    def agent_job(run: dict, path: Path) -> None:
        progress = {"step": None, "steps_done": []}
        trajectory = runs_dir / f"{run['id']}.trajectory.jsonl"

        def on_step(name: str, state: dict) -> None:
            if progress["step"]:
                progress["steps_done"].append(progress["step"])
            progress["step"] = name
            partial = {k: state[k] for k in ("findings", "suspects", "fixes", "tests_added") if k in state}
            save_run({**run, "status": "running", **progress, **partial})

        calls: list[dict] = []

        def record(call: dict) -> None:
            calls.append(call)
            with trajectory.open("a") as f:
                f.write(json.dumps(call) + "\n")
            if call.get("redactions"):
                audit.write("model.redacted", run_id=run["id"], step=call["step"], count=call["redactions"])

        save_run({**run, "status": "running", **progress})
        audit.write("run.started", run_id=run["id"])
        params = {"repo": run["repo"], "mode": "agents", "static_tools": tools,
                  "model": os.environ.get("LOCALI_MODEL_ID", "unknown")}
        try:
            with tracker.agent_run(run["id"], params):
                gated = guarded(tracker.wrap_model(model), record, step=lambda: progress["step"],
                                known=secret_values(path))
                state = run_workflow(path, run_id=run["id"], model=gated, store=patches, tools=tools,
                                     on_step=on_step, around_step=tracker.step)
                tracker.finish(run_metrics(state, calls), state["report"], trajectory)
        except Exception as e:  # noqa: BLE001 - any failure ends the run and is reported
            save_run({**run, "status": "failed", "error": redact(f"{type(e).__name__}: {e}"), **progress})
            audit.write("run.failed", run_id=run["id"], error=type(e).__name__)
            return
        save_run({**run, "status": "done", "step": None, "steps_done": state["steps"],
                  "report": state["report"], "patch_ids": state["patch_ids"], "patches": state["patches"],
                  "findings": state["findings"], "suspects": state["suspects"], "fixes": state["fixes"],
                  "tests_added": state["tests_added"], "docs": state["docs"], "tests_before": state.get("tests_before"),
                  "devops": state["devops"]})
        audit.write("run.finished", run_id=run["id"], patch_ids=state["patch_ids"])

    def resolve_repo(repo: str) -> Path:
        path = (repos_root / repo).resolve()
        if not path.is_relative_to(repos_root):
            audit.write("run.refused", repo=repo, reason="outside repos root")
            raise HTTPException(400, "repo must be inside the configured repos root")
        if not path.is_dir():
            audit.write("run.refused", repo=repo, reason="not found")
            raise HTTPException(404, "repo not found")
        return path

    @app.get("/playground/models")
    def playground_models():
        return [{"key": key, "id": model_id} for key, (model_id, _) in playground.items()]

    @app.post("/playground")
    async def playground_call(req: PlaygroundRequest):
        if req.model not in playground:
            raise HTTPException(404, f"no {req.model!r} model configured")
        try:
            messages = build_messages(req.task, req.language, code=redact(req.code), prompt=redact(req.prompt),
                                      test=redact(req.test), error=redact(req.error))
        except ValueError as e:
            raise HTTPException(422, str(e)) from None
        model_id, stream = playground[req.model]
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def work():
            try:
                done = stream(messages, lambda piece: loop.call_soon_threadsafe(queue.put_nowait, ("token", piece)))
                loop.call_soon_threadsafe(queue.put_nowait, ("done", done))
            except Exception as e:  # noqa: BLE001 - reported to the page
                loop.call_soon_threadsafe(queue.put_nowait, ("error", e))

        async def events():
            loop.run_in_executor(None, work)
            while True:
                kind, value = await queue.get()
                if kind == "token":
                    yield f"data: {json.dumps({'type': 'token', 'text': value})}\n\n"
                    continue
                if kind == "error":
                    audit.write("playground.failed", task=req.task, model=model_id, error=type(value).__name__)
                    yield f"data: {json.dumps({'type': 'error', 'message': redact(str(value))})}\n\n"
                    return
                answer = redact(value.text)
                audit.write("playground.call", task=req.task, language=req.language, model=model_id,
                            input_tokens=value.input_tokens, output_tokens=value.output_tokens)
                yield "data: " + json.dumps({
                    "type": "done", "answer": answer, "model": model_id, "input_tokens": value.input_tokens,
                    "output_tokens": value.output_tokens, "ttft_s": value.ttft_s, "total_s": value.total_s,
                }) + "\n\n"
                return

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    def read_audit() -> list[dict]:
        path = Path(data_dir) / "audit.jsonl"
        lines = path.read_text().splitlines() if path.exists() else []
        return [json.loads(line) for line in reversed(lines)]

    @app.get("/audit")
    def list_audit(action: str | None = None, limit: int = 200):
        events = [e for e in read_audit() if action is None or e["action"] == action]
        return events[: max(1, min(limit, 2000))]

    @app.get("/security/events")
    def security_events(limit: int = 200):
        events = [e for e in read_audit() if e["action"] in SECURITY_ACTIONS]
        return {"counts": dict(Counter(e["action"] for e in events)), "events": events[: max(1, min(limit, 2000))]}

    summary_path = Path(results_file) if results_file else RESULTS_FILE

    def load_summary() -> dict | None:
        return json.loads(summary_path.read_text()) if summary_path.exists() else None

    @app.get("/results")
    def results():
        summary = load_summary()
        if summary is None:
            raise HTTPException(404, "no results summary; run experiments/scripts/export_results.py")
        return summary

    @app.get("/models")
    def models():
        registry = json.loads(MODELS_FILE.read_text())
        measured = {(r["model"], r["quant"]): r for r in (load_summary() or {}).get("ladder", {}).get("rows", [])}
        out = []
        for m in registry["models"]:
            row = measured.get(("fine-tuned" if m["fine_tuned"] else "base", m["quant"]), {})
            out.append({**m, "laptop": row.get("tasks", {}), "peak_ram_gb": row.get("peak_ram_gb"),
                        "active": os.environ.get("LOCALI_MODEL_ID") == m["id"]})
        return {"note": registry["note"], "models": out}

    @app.get("/status")
    def status():
        return {"model_configured": model is not None, "static_analysis": tools,
                "mlflow_tracking": tracker.enabled, "mlflow_ui": os.environ.get("LOCALI_MLFLOW_UI")}

    @app.post("/runs", status_code=201)
    def create_run(req: RunRequest):
        if req.mode == "agents" and model is None:
            raise HTTPException(503, "no model configured for agent runs (set LOCALI_MODEL_URL)")
        path = resolve_repo(req.repo)
        if req.mode == "agents" and not python_files(path):
            raise HTTPException(422, "The full assistant works on Python code, and this repository has none. "
                                     "A quick scan works on JavaScript, TypeScript, Java and Go too.")
        run_id = uuid.uuid4().hex[:12]
        audit.write("run.created", run_id=run_id, repo=req.repo, mode=req.mode)
        if req.mode == "agents":
            run = {"id": run_id, "repo": req.repo, "mode": "agents", "status": "queued", "created": now()}
            save_run(run)
            app.state.agents.submit(agent_job, run, path)
            return JSONResponse(status_code=202, content=run)
        findings = [{**asdict(f), "message": redact(f.message)} for f in analyze(path)]
        run = {
            "id": run_id,
            "repo": req.repo,
            "mode": "analyze",
            "status": "done",
            "created": now(),
            "findings": findings,
            "summary": {
                "by_category": dict(Counter(f["category"] for f in findings)),
                "by_tool": dict(Counter(f["tool"] for f in findings)),
            },
        }
        save_run(run)
        audit.write("run.finished", run_id=run_id, findings=len(findings))
        return run

    def load_run(run_id: str) -> dict:
        path = runs_dir / f"{run_id}.json"
        if not run_id.isalnum() or not path.exists():
            raise HTTPException(404, "run not found")
        return json.loads(path.read_text())

    def all_runs() -> list[dict]:
        """Every run, newest first. Runs from before timestamps were recorded use the file's time."""
        runs = [{"created": _mtime(p), **json.loads(p.read_text())} for p in runs_dir.glob("*.json")]
        return sorted(runs, key=lambda r: r["created"], reverse=True)

    @app.get("/runs")
    def list_runs():
        summary_keys = ("id", "repo", "mode", "status", "step", "patch_ids", "error", "created")
        return [{k: r[k] for k in summary_keys if k in r} for r in all_runs()]

    def git_info(path: Path) -> dict | None:
        if not (path / ".git").exists():
            return None
        git = ["git", "-c", "core.fsmonitor=false", "-C", str(path)]
        log = run_command([*git, "log", "-1", "--format=%s%n%cI"], timeout=10)
        branch = run_command([*git, "rev-parse", "--abbrev-ref", "HEAD"], timeout=10)
        subject, _, date = log.stdout.strip().partition("\n") if log.returncode == 0 else ("", "", "")
        return {"branch": branch.stdout.strip() if branch.returncode == 0 else None,
                "last_commit": redact(subject) or None, "last_commit_date": date or None}

    @app.get("/repos")
    def list_repos():
        runs = all_runs()
        out = []
        for path in sorted(p for p in repos_root.iterdir() if p.is_dir()):
            if path.name.startswith(".") or path.name in SKIP_DIRS:
                continue
            languages = count_languages(path)
            if not languages:
                continue
            mine = [r for r in runs if r["repo"] == path.name]
            ids = {r["id"] for r in mine}
            agents = [r for r in mine if r["mode"] == "agents" and r["status"] == "done"]
            last = mine[0] if mine else None
            out.append({
                "name": path.name, "python_files": languages.get("python", 0), "languages": languages,
                "git": git_info(path), "runs": len(mine),
                "last_run": {k: last.get(k) for k in ("id", "mode", "status", "created")} if last else None,
                "open_patches": sum(p.run_id in ids and p.status in ("proposed", "approved") for p in patches.all()),
                "ready_to_merge": (agents[0].get("devops") or {}).get("ready_to_merge") if agents else None,
            })
        return out

    @app.get("/trends")
    def trends(repo: str):
        done = [r for r in all_runs() if r["repo"] == repo and r["status"] == "done"]
        return [trend_point(r) for r in reversed(done)]

    @app.get("/settings")
    def settings():
        env = os.environ.get
        variables = [
            ("LOCALI_REPOS_ROOT", "Folder whose sub-folders can be analysed", str(repos_root)),
            ("LOCALI_DATA_DIR", "Runs, patches and the audit log", str(Path(data_dir).resolve())),
            ("LOCALI_MODEL_URL", "OpenAI-compatible model server", _without_credentials(env("LOCALI_MODEL_URL"))),
            ("LOCALI_MODEL_NAME", "Model name sent to the server", env("LOCALI_MODEL_NAME")),
            ("LOCALI_MODEL_ID", "Which registry model is running (Models page)", env("LOCALI_MODEL_ID")),
            ("LOCALI_MODEL_KEY", "API key of the model server", "set" if env("LOCALI_MODEL_KEY") else None),
            ("LOCALI_API_TOKEN", "Token every API call must carry", "set" if api_token else None),
            ("LOCALI_COMPARE_URL", "Optional second model, shown beside the first in the playground",
             _without_credentials(env("LOCALI_COMPARE_URL"))),
            ("LOCALI_COMPARE_ID", "Which registry model the second server runs", env("LOCALI_COMPARE_ID")),
            ("LOCALI_MLFLOW_URI", "MLflow tracking store for agent runs", tracker.uri),
            ("LOCALI_MLFLOW_UI", "Link to the MLflow interface", env("LOCALI_MLFLOW_UI")),
        ]
        return {
            "repos_root": str(repos_root),
            "model": {"configured": model is not None, "url": _without_credentials(env("LOCALI_MODEL_URL")),
                      "name": env("LOCALI_MODEL_NAME"), "id": env("LOCALI_MODEL_ID"),
                      "key_set": bool(env("LOCALI_MODEL_KEY")), "max_tokens": 768},
            "api_token_set": bool(api_token),
            "workflow": {"steps": [s for s in STEPS if tools or s != "analyze"], "static_analysis": tools,
                         "routing": "fixed", "concurrent_runs": 1},
            "sandbox": {"image": sandbox.IMAGE, "network": False},
            "mlflow": {"tracking": tracker.enabled, "ui": env("LOCALI_MLFLOW_UI")},
            "variables": [{"env": k, "description": d, "value": v} for k, d, v in variables],
        }

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        run = load_run(run_id)  # 404 for an unknown id
        return {"created": _mtime(runs_dir / f"{run_id}.json"), **run}

    @app.get("/runs/{run_id}/trajectory")
    def get_trajectory(run_id: str):
        load_run(run_id)
        path = runs_dir / f"{run_id}.trajectory.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    @app.get("/runs/{run_id}/events")
    async def run_events(run_id: str):
        load_run(run_id)
        return StreamingResponse(event_stream(lambda: load_run(run_id), heartbeat_s), media_type="text/event-stream")

    def get_patch(patch_id: str):
        try:
            return patches.get(patch_id)
        except KeyError:
            raise HTTPException(404, "patch not found") from None

    def decide(action, *args, **kwargs):
        try:
            return asdict(action(*args, **kwargs))
        except KeyError:
            raise HTTPException(404, "patch not found") from None
        except (ApprovalMismatch, StalePatch, PatchConflict) as e:
            raise HTTPException(409, f"{type(e).__name__}: {e}") from None

    @app.get("/runs/{run_id}/patches")
    def list_patches(run_id: str):
        return [asdict(p) for p in patches.for_run(run_id)]

    @app.get("/patches")
    def list_all_patches(status: str | None = None):
        keys = ("id", "run_id", "repo", "files", "status", "reviewer", "sha256", "title", "kind")
        return [{k: getattr(p, k) for k in keys} | {"validation_ok": bool(p.validation.get("ok"))}
                for p in patches.all() if status is None or p.status == status]

    @app.get("/patches/{patch_id}")
    def show_patch(patch_id: str):
        return asdict(get_patch(patch_id))

    @app.post("/patches/{patch_id}/approve")
    def approve_patch(patch_id: str, body: Approval):
        return decide(patches.approve, patch_id, sha256=body.sha256, baseline=body.baseline,
                      validation_sha256=body.validation_sha256, reviewer=body.reviewer)

    @app.post("/patches/{patch_id}/reject")
    def reject_patch(patch_id: str, body: Rejection):
        return decide(patches.reject, patch_id, reviewer=body.reviewer)

    @app.post("/patches/{patch_id}/apply")
    def apply_patch(patch_id: str):
        return decide(patches.apply, patch_id)

    @app.post("/patches/{patch_id}/revert")
    def revert_patch(patch_id: str):
        return decide(patches.revert, patch_id)

    @app.post("/patches/{patch_id}/revalidate", status_code=201)
    def revalidate_patch(patch_id: str):
        old = get_patch(patch_id)
        if old.status not in ("stale", "proposed"):
            raise HTTPException(409, f"patch is {old.status}")
        ws = open_workspace(old.repo)
        try:
            # GNU patch tolerates shifted hunks (git apply anchors a hunk without leading context to
            # line 1); the result is a new proposal that is validated and reviewed from scratch.
            done = run_command(["patch", "-p1", "--batch", "--forward", "--fuzz=2", "--no-backup-if-mismatch"],
                               cwd=ws.path, input=old.diff)
            if done.returncode != 0:
                raise HTTPException(409, f"patch no longer applies: {(done.stdout + done.stderr).strip()[:300]}")
            diff = ws.diff()
            check = validate or (lambda path, files: validate_workspace(path, files, original=ws.repo, diff=diff))
            new = propose(ws, run_id=old.run_id, validate=check, store=patches)
        finally:
            ws.cleanup()
        audit.write("patch.revalidated", patch_id=old.id, new_patch_id=new.id)
        return asdict(new)

    return app


def _playground_model(client) -> PlaygroundModel:
    return lambda messages, on_token: client.complete(messages, max_tokens=1024, on_token=on_token)


def default_app() -> FastAPI:
    from backend.envfile import load_env
    from evaluation.client import ChatClient

    load_env(os.environ.get("LOCALI_ENV_FILE", Path(__file__).resolve().parents[1] / ".env"))

    model = None
    playground: dict[str, tuple[str, PlaygroundModel]] = {}
    if url := os.environ.get("LOCALI_MODEL_URL"):
        client = ChatClient(url, model=os.environ.get("LOCALI_MODEL_NAME", "local"),
                            api_key=os.environ.get("LOCALI_MODEL_KEY", "local"))

        def model(messages):
            return client.complete(messages, max_tokens=768)  # the run's guard reads text and token counts

        playground["main"] = (os.environ.get("LOCALI_MODEL_ID", "local"), _playground_model(client))
    if url := os.environ.get("LOCALI_COMPARE_URL"):  # optional second model, shown beside the first
        compare = ChatClient(url, model=os.environ.get("LOCALI_COMPARE_NAME", "local"),
                             api_key=os.environ.get("LOCALI_COMPARE_KEY", "local"))
        playground["compare"] = (os.environ.get("LOCALI_COMPARE_ID", "compare"), _playground_model(compare))
    token = os.environ.get("LOCALI_API_TOKEN")
    if not token:
        raise RuntimeError("set LOCALI_API_TOKEN; the API does not run without a token")
    return create_app(os.environ.get("LOCALI_REPOS_ROOT", "."), os.environ.get("LOCALI_DATA_DIR", "data/backend"),
                      model=model, api_token=token, mlflow_uri=os.environ.get("LOCALI_MLFLOW_URI"),
                      mlflow_artifacts=os.environ.get("LOCALI_MLFLOW_ARTIFACTS"), playground=playground)
