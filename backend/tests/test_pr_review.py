import subprocess

import pytest

from backend.pr_review import review_range

GIT = ["-c", "user.name=t", "-c", "user.email=t@t"]


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *GIT, *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    (r / "old.py").write_text("def run(x):\n    return eval(x)\n")
    (r / "util.py").write_text("def add(a, b):\n    return a + b\n")
    git(r, "init", "-q", "-b", "main")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "base")
    return r


def commit(repo, msg="head"):
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", msg)
    return git(repo, "rev-parse", "HEAD").strip()


def test_new_vulnerability_in_changed_file_is_reported_and_blocks(repo):
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "util.py").write_text("import subprocess\n\n\ndef add(a, b):\n    subprocess.run(f'echo {a}', shell=True)\n    return a + b\n")
    head = commit(repo)
    result = review_range(repo, base, head)
    assert result.blocking and any(f["path"] == "util.py" and f["category"] == "security" for f in result.new_findings)
    assert "util.py" in result.markdown and "shell" in result.markdown.lower()


def test_old_findings_in_unchanged_files_are_not_reported(repo):
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "util.py").write_text("def add(a, b):\n    return b + a\n")
    head = commit(repo)
    result = review_range(repo, base, head)
    assert not result.blocking and result.new_findings == []
    assert "old.py" not in result.markdown


def test_secret_in_added_lines_blocks(repo):
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "config.py").write_text('API_TOKEN = "' + "q8Zt4Lm" + 'Wp2Xc9Rv7Kd1Nf"\n')
    head = commit(repo)
    result = review_range(repo, base, head)
    assert result.blocking and result.secrets == ["config.py: generic-secret"]
    assert "q8Zt4Lm" not in result.markdown


def test_clean_change_passes_with_a_short_comment(repo):
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "notes.md").write_text("# notes\n")
    head = commit(repo)
    result = review_range(repo, base, head)
    assert not result.blocking and "No new findings" in result.markdown
