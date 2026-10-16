import json
from pathlib import Path

from backend.analysis import analyze

ROOT = Path(__file__).resolve().parents[2]

SAMPLE = '''import os
import subprocess


def run(cmd):
    return subprocess.call(cmd, shell=True)


def calc(expr):
    return eval(expr)


def grade(x):
    if x > 90:
        return "A"
    elif x > 80:
        return "B"
    elif x > 70:
        return "C"
    elif x > 60:
        return "D"
    elif x > 50:
        return "E"
    elif x > 40:
        return "F"
    elif x > 30:
        return "G"
    elif x > 20:
        return "H"
    elif x > 10:
        return "I"
    elif x > 5:
        return "J"
    return "K"
'''


def by_tool(findings, tool):
    return {(f.path, f.line) for f in findings if f.tool == tool}


def test_each_tool_reports_with_relative_path_and_line(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text(SAMPLE)
    findings = analyze(tmp_path)

    assert ("pkg/mod.py", 1) in by_tool(findings, "ruff")  # unused import os
    assert ("pkg/mod.py", 6) in by_tool(findings, "bandit")
    assert ("pkg/mod.py", 10) in by_tool(findings, "semgrep")
    assert ("pkg/mod.py", 13) in by_tool(findings, "radon")
    assert {f.category for f in findings} <= {"bug", "security", "quality"}
    assert {f.severity for f in findings} <= {"high", "medium", "low"}


def test_clean_code_has_no_findings(tmp_path):
    (tmp_path / "ok.py").write_text("def add(a, b):\n    return a + b\n")
    assert analyze(tmp_path) == []


def test_finds_every_planted_vulnerability_in_demo_repo():
    flaws = json.loads((ROOT / "security" / "demo_repo_flaws.json").read_text())["flaws"]
    found = {(f.path, f.line) for f in analyze(ROOT / "demo_repo") if f.category == "security"}
    missed = [x["id"] for x in flaws if x["kind"] == "security" and (x["file"], x["line"]) not in found]
    assert missed == []


def test_planted_injections_in_demo_repo_are_reported():
    files = {f.path for f in analyze(ROOT / "demo_repo") if f.tool == "injection"}
    assert files == {"README.md", "docs/issues/ISSUE-12.md"}
