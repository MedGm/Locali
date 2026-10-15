"""HTTP API of the assistant.

    uv run uvicorn backend.app:default_app --factory --reload

Only folders under LOCALI_REPOS_ROOT can be analysed. Every message leaving the backend goes
through secret redaction, and every action is appended to <data dir>/audit.jsonl.

Agent changes arrive as validated patches (backend.patches). A reviewer approves one exact patch
by sending back its SHA-256 and baseline; only then can it be applied, and it can be reverted.
A patch that went stale (the folder changed) is revalidated into a new proposal.
"""

import json
import os
import subprocess
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.analysis import analyze
from backend.audit import AuditLog
from backend.patches import ApprovalMismatch, PatchConflict, PatchStore, StalePatch, propose
from backend.validation import validate_workspace
from backend.workspace import open_workspace
from security.secrets import redact


class RunRequest(BaseModel):
    repo: str


class Approval(BaseModel):
    sha256: str
    baseline: dict[str, str | None]
    reviewer: str


class Rejection(BaseModel):
    reviewer: str


def create_app(repos_root: str | Path, data_dir: str | Path,
               validate: Callable[[Path, list[str]], dict] | None = None) -> FastAPI:
    """validate replaces the full workspace validation (tests use a stub)."""
    repos_root = Path(repos_root).resolve()
    runs_dir = Path(data_dir) / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    audit = AuditLog(Path(data_dir) / "audit.jsonl")
    patches = PatchStore(Path(data_dir), audit)
    app = FastAPI(title="Locali")
    app.state.patches = patches

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

    @app.get("/patches/{patch_id}")
    def show_patch(patch_id: str):
        return asdict(get_patch(patch_id))

    @app.post("/patches/{patch_id}/approve")
    def approve_patch(patch_id: str, body: Approval):
        return decide(patches.approve, patch_id, sha256=body.sha256, baseline=body.baseline, reviewer=body.reviewer)

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
            done = subprocess.run(["patch", "-p1", "--batch", "--forward", "--fuzz=2", "--no-backup-if-mismatch"],
                                  cwd=ws.path, input=old.diff, capture_output=True, text=True, check=False)
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


def default_app() -> FastAPI:
    return create_app(os.environ.get("LOCALI_REPOS_ROOT", "."), os.environ.get("LOCALI_DATA_DIR", "data/backend"))
