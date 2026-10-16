from pathlib import Path

from backend.agents.devops import ci_status, dependency_risks, devops_summary

DEMO = Path(__file__).resolve().parents[2] / "demo_repo"


def test_typosquatted_dependency_is_flagged_and_real_ones_are_not(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\nreqeusts==2.31.0\nnumpy>=1.26\n# comment\nflsk\n")
    risks = dependency_risks(tmp_path)
    assert [(r["name"], r["looks_like"]) for r in risks] == [("reqeusts", "requests"), ("flsk", "flask")]


def test_demo_repo_typosquat_is_found():
    assert [r["name"] for r in dependency_risks(DEMO)] == ["reqeusts"]


def test_ci_status_detects_workflows(tmp_path):
    assert ci_status(tmp_path) == {"has_ci": False, "has_locali_review": False, "workflows": []}
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: CI\n")
    assert ci_status(tmp_path)["has_ci"] is True


def test_summary_lists_blockers_and_suggests_ci(tmp_path):
    (tmp_path / "requirements.txt").write_text("reqeusts==1.0\n")
    state = {
        "findings": [{"category": "security", "severity": "high", "tool": "bandit", "path": "a.py", "line": 3},
                     {"category": "security", "severity": "high", "tool": "secrets", "path": "s.py", "line": 1}],
        "patches": [{"id": "p1", "kind": "fix", "title": "Fix f", "ok": True}],
        "fixes": [{"fixed": True}], "suspects": [{}],
    }
    summary = devops_summary(tmp_path, state, tests_before={"passed": 5, "failed": ["t::x"], "coverage_percent": 35.1})
    assert summary["ready_to_merge"] is False
    assert any("secret" in b for b in summary["blockers"]) and any("reqeusts" in b for b in summary["blockers"])
    assert summary["suggested_workflow"] and "locali" in summary["suggested_workflow"].lower()
    assert "## DevOps summary" in summary["markdown"]
