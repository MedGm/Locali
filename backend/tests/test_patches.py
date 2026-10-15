import subprocess

import pytest

from backend.patches import ApprovalMismatch, PatchConflict, PatchStore, StalePatch, propose
from backend.workspace import open_workspace


def no_checks(path, files):
    return {"tests": "skipped", "ok": True}


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    (root / "app.py").write_text("def add(a, b):\n    return a - b\n")
    (root / "README.md").write_text("demo\n")
    return root


@pytest.fixture
def store(tmp_path):
    return PatchStore(tmp_path / "data")


def fix_and_add_test(repo, store, validate=no_checks):
    ws = open_workspace(repo)
    (ws.path / "app.py").write_text("def add(a, b):\n    return a + b\n")
    (ws.path / "test_app.py").write_text("from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    patch = propose(ws, run_id="r1", validate=validate, store=store)
    ws.cleanup()
    return patch


def test_proposal_records_diff_hash_files_baseline_and_validation(repo, store):
    patch = fix_and_add_test(repo, store)
    assert patch.status == "proposed"
    assert sorted(patch.files) == ["app.py", "test_app.py"]
    assert patch.baseline["app.py"] and patch.baseline["test_app.py"] is None
    assert len(patch.sha256) == 64 and "+    return a + b" in patch.diff
    assert patch.validation == {"tests": "skipped", "ok": True}
    assert store.get(patch.id) == patch
    assert "a - b" in (repo / "app.py").read_text()  # nothing applied yet


def test_validation_sees_the_workspace_and_the_changed_files(repo, store):
    seen = {}

    def validate(path, files):
        seen["code"] = (path / "app.py").read_text()
        seen["files"] = sorted(files)
        return {"ok": True}

    fix_and_add_test(repo, store, validate)
    assert "a + b" in seen["code"] and seen["files"] == ["app.py", "test_app.py"]


def test_no_changes_means_no_proposal(repo, store):
    ws = open_workspace(repo)
    assert propose(ws, run_id="r1", validate=no_checks, store=store) is None
    ws.cleanup()


def test_approval_must_name_the_exact_patch_and_baseline(repo, store):
    patch = fix_and_add_test(repo, store)
    with pytest.raises(ApprovalMismatch):
        store.approve(patch.id, sha256="0" * 64, baseline=patch.baseline, reviewer="me")
    with pytest.raises(ApprovalMismatch):
        store.approve(patch.id, sha256=patch.sha256, baseline={**patch.baseline, "app.py": "x"}, reviewer="me")
    approved = store.approve(patch.id, sha256=patch.sha256, baseline=patch.baseline, reviewer="me")
    assert approved.status == "approved" and approved.reviewer == "me"


def test_failed_validation_cannot_be_approved(repo, store):
    patch = fix_and_add_test(repo, store, validate=lambda p, f: {"ok": False})
    with pytest.raises(ApprovalMismatch):
        store.approve(patch.id, sha256=patch.sha256, baseline=patch.baseline, reviewer="me")


def test_apply_requires_approval_then_changes_the_repo_and_keeps_a_backup(repo, store):
    patch = fix_and_add_test(repo, store)
    with pytest.raises(ApprovalMismatch):
        store.apply(patch.id)
    store.approve(patch.id, sha256=patch.sha256, baseline=patch.baseline, reviewer="me")
    applied = store.apply(patch.id)
    assert applied.status == "applied"
    assert "a + b" in (repo / "app.py").read_text() and (repo / "test_app.py").exists()

    reverted = store.revert(patch.id)
    assert reverted.status == "reverted"
    assert "a - b" in (repo / "app.py").read_text() and not (repo / "test_app.py").exists()


def test_repo_changed_since_proposal_makes_the_patch_stale(repo, store):
    patch = fix_and_add_test(repo, store)
    store.approve(patch.id, sha256=patch.sha256, baseline=patch.baseline, reviewer="me")
    (repo / "app.py").write_text("def add(a, b):\n    return b - a\n")
    with pytest.raises(StalePatch):
        store.apply(patch.id)
    assert store.get(patch.id).status == "stale"
    assert "b - a" in (repo / "app.py").read_text()


def test_conflicting_new_file_is_refused_before_anything_is_written(repo, store):
    patch = fix_and_add_test(repo, store)
    store.approve(patch.id, sha256=patch.sha256, baseline=patch.baseline, reviewer="me")
    (repo / "test_app.py").write_text("# someone else's test\n")
    with pytest.raises((StalePatch, PatchConflict)):
        store.apply(patch.id)
    assert "a - b" in (repo / "app.py").read_text()


def test_apply_works_for_a_folder_inside_a_git_repo(tmp_path, store):
    top = tmp_path / "top"
    (top / "shop").mkdir(parents=True)
    (top / "shop" / "app.py").write_text("def add(a, b):\n    return a - b\n")
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"]):
        subprocess.run(["git", "-C", str(top), *args], check=True)
    patch = fix_and_add_test(top / "shop", store)
    store.approve(patch.id, sha256=patch.sha256, baseline=patch.baseline, reviewer="me")
    store.apply(patch.id)
    assert "a + b" in (top / "shop" / "app.py").read_text()
    assert (top / "shop" / "test_app.py").exists() and not (top / "test_app.py").exists()
