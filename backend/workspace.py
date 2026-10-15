"""Isolated workspaces where agents make changes, never in the user's working tree.

- worktree: the repository is in Git and the folder has no uncommitted or untracked changes. A
  detached `git worktree` at HEAD; branches and the user's checkout are untouched.
- snapshot: anything else (no Git, or local changes a worktree at HEAD would miss). A copy without
  .git, virtualenvs and caches, with a throwaway Git repository and a baseline commit inside.

Both give the same thing back: `diff()` is a Git unified diff relative to the folder, which
`git apply` can check and apply to the real folder whether or not it is a Git repository.
"""

import hashlib
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from security.commands import CompletedProcess
from security.commands import run as run_command

SKIP = (".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache")
_IDENTITY = ["-c", "user.name=locali", "-c", "user.email=locali@localhost"]


def _git(cwd: Path, *args: str, check: bool = True) -> CompletedProcess:
    return run_command(["git", "-C", str(cwd), *_IDENTITY, *args], check=check)


def file_hash(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


@dataclass
class Workspace:
    kind: str  # "worktree" or "snapshot"
    repo: Path  # the user's folder
    path: Path  # where the agent works
    head: str | None  # Git commit the folder was at, if any
    _tmp: Path
    _toplevel: Path | None = None

    def diff(self) -> str:
        _git(self.path, "add", "-A", "--", ".")
        return _git(self.path, "diff", "--cached", "--binary", "--relative", "HEAD", "--", ".").stdout

    def baseline_hashes(self, rel_paths: list[str]) -> dict[str, str | None]:
        return {p: file_hash(self.repo / p) for p in rel_paths}

    def cleanup(self) -> None:
        if self.kind == "worktree" and self._toplevel is not None:
            _git(self._toplevel, "worktree", "remove", "--force", str(self._tmp / "wt"), check=False)
            _git(self._toplevel, "worktree", "prune", check=False)
        shutil.rmtree(self._tmp, ignore_errors=True)


def _toplevel(repo: Path) -> Path | None:
    out = _git(repo, "rev-parse", "--show-toplevel", check=False)
    return Path(out.stdout.strip()).resolve() if out.returncode == 0 else None


def open_workspace(repo: str | Path) -> Workspace:
    repo = Path(repo).resolve()
    tmp = Path(tempfile.mkdtemp(prefix="locali-ws-"))
    top = _toplevel(repo)
    head = _git(repo, "rev-parse", "HEAD").stdout.strip() if top else None

    if top is not None and _git(repo, "status", "--porcelain", "--", ".").stdout == "":
        _git(top, "worktree", "add", "--detach", str(tmp / "wt"), "HEAD")
        return Workspace("worktree", repo, tmp / "wt" / repo.relative_to(top), head, tmp, top)

    path = tmp / "snapshot"
    shutil.copytree(repo, path, ignore=shutil.ignore_patterns(*SKIP), symlinks=True)
    _git(path, "init", "-q")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "baseline", "--allow-empty")
    return Workspace("snapshot", repo, path, head, tmp)
