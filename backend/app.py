"""HTTP API of the assistant.

    uv run uvicorn backend.app:default_app --factory --reload

Only folders under LOCALI_REPOS_ROOT can be analysed. Every message leaving the backend goes
through secret redaction, and every action is appended to <data dir>/audit.jsonl.
"""

import json
import os
import uuid
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.analysis import analyze
from backend.audit import AuditLog
from security.secrets import redact


class RunRequest(BaseModel):
    repo: str


def create_app(repos_root: str | Path, data_dir: str | Path) -> FastAPI:
    repos_root = Path(repos_root).resolve()
    runs_dir = Path(data_dir) / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    audit = AuditLog(Path(data_dir) / "audit.jsonl")
    app = FastAPI(title="Locali")

    def resolve_repo(repo: str) -> Path:
        path = (repos_root / repo).resolve()
        if not path.is_relative_to(repos_root):
            audit.write("run.refused", repo=repo, reason="outside repos root")
            raise HTTPException(400, "repo must be inside the configured repos root")
        if not path.is_dir():
            audit.write("run.refused", repo=repo, reason="not found")
            raise HTTPException(404, "repo not found")
        return path

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/runs", status_code=201)
    def create_run(req: RunRequest):
        path = resolve_repo(req.repo)
        run_id = uuid.uuid4().hex[:12]
        audit.write("run.created", run_id=run_id, repo=req.repo)
        findings = [{**asdict(f), "message": redact(f.message)} for f in analyze(path)]
        run = {
            "id": run_id,
            "repo": req.repo,
            "status": "done",
            "findings": findings,
            "summary": {
                "by_category": dict(Counter(f["category"] for f in findings)),
                "by_tool": dict(Counter(f["tool"] for f in findings)),
            },
        }
        (runs_dir / f"{run_id}.json").write_text(json.dumps(run))
        audit.write("run.finished", run_id=run_id, findings=len(findings))
        return run

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        path = runs_dir / f"{run_id}.json"
        if not run_id.isalnum() or not path.exists():
            raise HTTPException(404, "run not found")
        return json.loads(path.read_text())

    return app


def default_app() -> FastAPI:
    return create_app(os.environ.get("LOCALI_REPOS_ROOT", "."), os.environ.get("LOCALI_DATA_DIR", "data/backend"))
