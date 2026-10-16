"""Validated patches: the only way agent work reaches the user's folder.

An agent works in an isolated workspace (backend.workspace) and proposes its changes as one patch:
the unified diff, its SHA-256, the files it touches with the hash each had in the user's folder
(the baseline), and a validation record. A patch moves through

    proposed -> approved -> applied -> reverted
             -> rejected     \\-> stale (folder changed after the proposal)

Approval names the exact patch hash, baseline and validation-record hash (what the reviewer saw),
and only a patch whose validation passed can be approved. The stored record is re-hashed at
approval, so a record edited after the proposal is refused. Applying re-hashes the files first (any change makes the patch stale), checks the diff
with `git apply --check`, backs up the files it will overwrite, then applies. Revert restores the
backups and removes the files the patch created, but only if the files are still exactly as the
patch left them; otherwise it would overwrite later work.

Every state change runs under a lock per user folder (flock, so it also holds across processes):
re-hashing, checking and writing happen as one step, and patch records are written atomically.
"""

import fcntl
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path

from backend.audit import AuditLog
from backend.workspace import Workspace, file_hash
from security.commands import CompletedProcess
from security.commands import run as run_command

_DIFF_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$", re.MULTILINE)


class ApprovalMismatch(Exception):
    """The decision does not match the patch, or the patch is not in a state that allows it."""


class StalePatch(Exception):
    """A touched file changed in the user's folder after the patch was proposed."""


class PatchConflict(Exception):
    """`git apply --check` refused the patch."""


@dataclass
class Patch:
    id: str
    run_id: str
    repo: str
    diff: str
    sha256: str
    files: list[str]
    baseline: dict[str, str | None]
    head: str | None
    validation: dict
    validation_sha256: str = ""
    title: str = ""
    kind: str = "change"  # "fix" (repairs code), "tests" (adds tests), "change" (anything else)
    applied_hashes: dict[str, str | None] = field(default_factory=dict)
    status: str = "proposed"
    reviewer: str | None = None
    history: list[str] = field(default_factory=list)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def validation_hash(validation: dict) -> str:
    return _sha(json.dumps(validation, sort_keys=True, separators=(",", ":"), default=str))


def _touched(diff: str) -> list[str]:
    return sorted({b for _, b in _DIFF_HEADER.findall(diff)})


def _git_apply(repo: Path, diff: str, *flags: str) -> CompletedProcess:
    """Run `git apply` so paths resolve against `repo`, also when it sits inside a larger Git repo."""
    top = run_command(["git", "-C", str(repo), "rev-parse", "--show-toplevel"])
    if top.returncode == 0:
        root = Path(top.stdout.strip()).resolve()
        rel = repo.resolve().relative_to(root).as_posix()
        args = ["git", "-C", str(root), "apply", *flags, *([f"--directory={rel}"] if rel != "." else [])]
    else:
        args = ["git", "-C", str(repo), "apply", *flags]
    return run_command([*args, "-"], input=diff)


class PatchStore:
    def __init__(self, data_dir: str | Path, audit: AuditLog | None = None):
        self.dir = Path(data_dir)
        (self.dir / "patches").mkdir(parents=True, exist_ok=True)
        (self.dir / "backups").mkdir(parents=True, exist_ok=True)
        (self.dir / "locks").mkdir(parents=True, exist_ok=True)
        self.audit = audit

    @contextmanager
    def _locked(self, patch_id: str) -> Iterator[Patch]:
        """Hold the lock of the patch's folder and yield a fresh copy of the patch read under it."""
        repo = self.get(patch_id).repo
        lock_path = self.dir / "locks" / f"{_sha(str(Path(repo).resolve()))[:16]}.lock"
        with open(lock_path, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield self.get(patch_id)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _log(self, action: str, patch: Patch, **extra) -> None:
        patch.history.append(action)
        if self.audit:
            self.audit.write(action, patch_id=patch.id, run_id=patch.run_id, sha256=patch.sha256, **extra)

    def save(self, patch: Patch) -> Patch:
        fd, tmp = tempfile.mkstemp(dir=self.dir / "patches", suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(asdict(patch), indent=1))
        os.replace(tmp, self.dir / "patches" / f"{patch.id}.json")
        return patch

    def get(self, patch_id: str) -> Patch:
        path = self.dir / "patches" / f"{patch_id}.json"
        if not patch_id.isalnum() or not path.exists():
            raise KeyError(patch_id)
        return Patch(**json.loads(path.read_text()))

    def all(self) -> list[Patch]:
        files = sorted((self.dir / "patches").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [Patch(**json.loads(p.read_text())) for p in files]

    def for_run(self, run_id: str) -> list[Patch]:
        patches = [Patch(**json.loads(p.read_text())) for p in sorted((self.dir / "patches").glob("*.json"))]
        return [p for p in patches if p.run_id == run_id]

    def approve(self, patch_id: str, *, sha256: str, baseline: dict, validation_sha256: str,
                reviewer: str) -> Patch:
        with self._locked(patch_id) as patch:
            if patch.status != "proposed":
                raise ApprovalMismatch(f"patch is {patch.status}, not proposed")
            if validation_hash(patch.validation) != patch.validation_sha256:
                raise ApprovalMismatch("stored validation record does not match its hash")
            if not patch.validation.get("ok"):
                raise ApprovalMismatch("patch failed validation")
            if sha256 != patch.sha256 or baseline != patch.baseline or validation_sha256 != patch.validation_sha256:
                raise ApprovalMismatch("decision does not match the proposed patch")
            patch.status, patch.reviewer = "approved", reviewer
            self._log("patch.approved", patch, reviewer=reviewer)
            return self.save(patch)

    def reject(self, patch_id: str, *, reviewer: str) -> Patch:
        with self._locked(patch_id) as patch:
            if patch.status not in ("proposed", "approved", "stale"):
                raise ApprovalMismatch(f"patch is {patch.status}")
            patch.status, patch.reviewer = "rejected", reviewer
            self._log("patch.rejected", patch, reviewer=reviewer)
            return self.save(patch)

    def apply(self, patch_id: str) -> Patch:
        with self._locked(patch_id) as patch:
            if patch.status != "approved":
                raise ApprovalMismatch(f"patch is {patch.status}, not approved")
            repo = Path(patch.repo)
            current = {f: file_hash(repo / f) for f in patch.files}
            if current != patch.baseline:
                patch.status = "stale"
                self._log("patch.stale", patch, changed=[f for f in patch.files if current[f] != patch.baseline[f]])
                self.save(patch)
                raise StalePatch("files changed since the patch was proposed; revalidate it")
            check = _git_apply(repo, patch.diff, "--check")
            if check.returncode != 0:
                self._log("patch.conflict", patch, error=check.stderr.strip()[:500])
                self.save(patch)
                raise PatchConflict(check.stderr.strip())
            backup = self.dir / "backups" / patch.id
            for f in patch.files:
                if patch.baseline[f] is not None:
                    (backup / f).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(repo / f, backup / f)
            done = _git_apply(repo, patch.diff)
            if done.returncode != 0:
                raise PatchConflict(done.stderr.strip())
            patch.applied_hashes = {f: file_hash(repo / f) for f in patch.files}
            patch.status = "applied"
            self._log("patch.applied", patch)
            return self.save(patch)

    def revert(self, patch_id: str) -> Patch:
        with self._locked(patch_id) as patch:
            if patch.status != "applied":
                raise ApprovalMismatch(f"patch is {patch.status}, not applied")
            repo, backup = Path(patch.repo), self.dir / "backups" / patch.id
            if {f: file_hash(repo / f) for f in patch.files} != patch.applied_hashes:
                self._log("patch.revert_refused", patch)
                self.save(patch)
                raise StalePatch("files changed after the patch was applied; reverting would overwrite that")
            for f in patch.files:
                if patch.baseline[f] is None:
                    (repo / f).unlink(missing_ok=True)
                else:
                    shutil.copy2(backup / f, repo / f)
            patch.status = "reverted"
            self._log("patch.reverted", patch)
            return self.save(patch)


def propose(ws: Workspace, *, run_id: str, validate: Callable[[Path, list[str]], dict],
            store: PatchStore, paths: list[str] | None = None, title: str = "", kind: str = "change") -> Patch | None:
    """Turn the workspace's changes (or only those to `paths`) into a validated, stored proposal
    (None if nothing changed)."""
    diff = ws.diff(paths)
    if not diff.strip():
        return None
    files = _touched(diff)
    validation = validate(ws.path, files)
    patch = Patch(id=uuid.uuid4().hex[:12], run_id=run_id, repo=str(ws.repo), diff=diff, sha256=_sha(diff),
                  files=files, baseline=ws.baseline_hashes(files), head=ws.head,
                  validation=validation, validation_sha256=validation_hash(validation), title=title, kind=kind)
    store._log("patch.proposed", patch, files=files, validation_ok=bool(patch.validation.get("ok")))
    return store.save(patch)
