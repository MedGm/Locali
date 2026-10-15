"""Validation of an agent's workspace before its patch can be approved.

A patch is ok when the repository's tests pass in the sandbox, the changed files gain no new
Bandit/Semgrep findings, and the added lines contain no secrets. Findings that were already in a
touched file do not block a fix to it: findings are compared per (file, tool, rule) count against
the user's original folder.
"""

from collections import Counter
from dataclasses import asdict
from pathlib import Path

from backend.analysis import bandit, semgrep
from security.secrets import scan_text

SECURITY_TOOLS = (bandit, semgrep)


def _security(root: Path, files: set[str]) -> list[dict]:
    return [asdict(f) for tool in SECURITY_TOOLS for f in tool(root) if f.path in files]


def _added_lines(diff: str) -> str:
    return "\n".join(line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))


def validate_workspace(path: Path, files: list[str], *, original: Path, diff: str, run_tests: bool = True) -> dict:
    from mcp_servers.tests_server import run_tests as sandbox_tests

    path, original, touched = Path(path).resolve(), Path(original).resolve(), set(files)
    tests = sandbox_tests(path) if run_tests else None

    before = Counter((f["path"], f["tool"], f["rule"]) for f in _security(original, touched))
    after = _security(path, touched)
    counts = Counter((f["path"], f["tool"], f["rule"]) for f in after)
    new_keys = {k for k, n in counts.items() if n > before[k]}
    new_findings = [f for f in after if (f["path"], f["tool"], f["rule"]) in new_keys]

    secrets = sorted({s.rule for s in scan_text(_added_lines(diff))})
    tests_ok = tests is None or (not tests["failed"] and not tests["errors"] and not tests["timed_out"])
    return {
        "ok": tests_ok and not new_findings and not secrets,
        "tests": tests,
        "new_security_findings": new_findings,
        "secrets_added": secrets,
    }
