import subprocess
from pathlib import Path

import pytest

from backend.workspace import open_workspace


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def add(a, b):\n    return a - b\n")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    return repo


@pytest.fixture
def plain_dir(tmp_path):
    repo = tmp_path / "plain"
    (repo / ".venv").mkdir(parents=True)
    (repo / ".venv" / "big.bin").write_text("x")
    (repo / "app.py").write_text("def add(a, b):\n    return a - b\n")
    return repo


def edit(ws):
    (ws.path / "app.py").write_text("def add(a, b):\n    return a + b\n")


def test_clean_git_repo_uses_a_worktree_and_leaves_the_repo_alone(git_repo):
    branches = git(git_repo, "branch", "--list")
    ws = open_workspace(git_repo)
    assert ws.kind == "worktree"
    assert ws.head == git(git_repo, "rev-parse", "HEAD").strip()
    edit(ws)
    assert "return a - b" in (git_repo / "app.py").read_text()
    assert "-    return a - b\n+    return a + b" in ws.diff()
    ws.cleanup()
    assert not ws.path.exists()
    assert str(ws.path) not in git(git_repo, "worktree", "list")
    assert git(git_repo, "branch", "--list") == branches
    assert git(git_repo, "status", "--porcelain") == ""


def test_uncommitted_changes_fall_back_to_a_snapshot_that_includes_them(git_repo):
    (git_repo / "app.py").write_text("def add(a, b):\n    return a * b\n")
    ws = open_workspace(git_repo)
    assert ws.kind == "snapshot"
    assert "a * b" in (ws.path / "app.py").read_text()
    ws.cleanup()


def test_plain_folder_snapshot_skips_virtualenvs_and_diffs_like_git(plain_dir):
    ws = open_workspace(plain_dir)
    assert ws.kind == "snapshot" and ws.head is None
    assert not (ws.path / ".venv").exists()
    edit(ws)
    (ws.path / "test_app.py").write_text("from app import add\n")
    diff = ws.diff()
    assert "+++ b/app.py" in diff and "+++ b/test_app.py" in diff
    assert "a - b" in (plain_dir / "app.py").read_text()
    ws.cleanup()
    assert not ws.path.exists()


def test_baseline_hashes_describe_the_original_files(plain_dir):
    ws = open_workspace(plain_dir)
    hashes = ws.baseline_hashes(["app.py", "missing.py"])
    assert len(hashes["app.py"]) == 64 and hashes["missing.py"] is None
    ws.cleanup()


def test_folder_inside_a_git_repo_gets_a_worktree_with_paths_relative_to_it(git_repo):
    sub = git_repo / "shop"
    sub.mkdir()
    (sub / "cart.py").write_text("TOTAL = 1\n")
    git(git_repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    git(git_repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "shop")
    ws = open_workspace(sub)
    assert ws.kind == "worktree" and ws.path.name == "shop"
    (ws.path / "cart.py").write_text("TOTAL = 2\n")
    diff = ws.diff()
    assert "+++ b/cart.py" in diff and "shop/" not in diff
    ws.cleanup()


def test_diff_can_be_limited_to_some_files(plain_dir):
    ws = open_workspace(plain_dir)
    edit(ws)
    (ws.path / "test_app.py").write_text("from app import add\n")
    only_test = ws.diff(["test_app.py"])
    assert "+++ b/test_app.py" in only_test and "app.py\n" not in only_test.replace("test_app.py", "")
    assert "+++ b/app.py" in ws.diff(["app.py"]) and "test_app.py" not in ws.diff(["app.py"])
    ws.cleanup()
