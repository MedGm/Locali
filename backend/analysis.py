"""Static analysis of a project folder: Ruff, Bandit, Radon, Semgrep, the secret scanner and the
prompt-injection detector.

Findings use the categories and severities of the T3 review format (bug / security / quality,
high / medium / low), so tool output and model reviews can be merged and compared.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from security.commands import run as run_command

RULES = Path(__file__).with_name("semgrep_rules.yml")
RUFF_SELECT = "F,E7,E9,B"
SKIP_DIRS = ".venv,venv,.git,node_modules,__pycache__"


@dataclass(frozen=True)
class Finding:
    tool: str
    rule: str
    path: str
    line: int
    category: str
    severity: str
    message: str


def _run(args: list[str]) -> str:
    return run_command(args).stdout


def _rel(root: Path, path: str) -> str:
    return Path(path).resolve().relative_to(root).as_posix()


def ruff(root: Path) -> list[Finding]:
    out = _run([sys.executable, "-m", "ruff", "check", "--isolated", "--no-cache", "--select", RUFF_SELECT,
                "--output-format", "json", str(root)])
    found = []
    for r in json.loads(out or "[]"):
        code = r["code"] or "E999"
        is_bug = code.startswith(("B", "E9", "F82"))
        severity = "high" if code.startswith(("E9", "F82")) else "medium" if code.startswith("B") else "low"
        found.append(Finding("ruff", code, _rel(root, r["filename"]), r["location"]["row"],
                             "bug" if is_bug else "quality", severity, r["message"]))
    return found


def bandit(root: Path) -> list[Finding]:
    out = _run([sys.executable, "-m", "bandit", "-r", "-q", "-f", "json", "-x", SKIP_DIRS, str(root)])
    return [
        Finding("bandit", r["test_id"], _rel(root, r["filename"]), r["line_number"], "security",
                r["issue_severity"].lower(), r["issue_text"])
        for r in json.loads(out or "{}").get("results", [])
        if r["issue_severity"] in ("MEDIUM", "HIGH")
    ]


def radon(root: Path) -> list[Finding]:
    """Functions with cyclomatic complexity rank C or worse (complexity > 10)."""
    out = _run([sys.executable, "-m", "radon", "cc", "-j", "-n", "C", "-e", "*/.venv/*", str(root)])
    found = []
    for path, blocks in json.loads(out or "{}").items():
        if not isinstance(blocks, list):  # radon reports parse errors as a dict
            continue
        for b in blocks:
            severity = "high" if b["rank"] == "F" else "medium" if b["rank"] in "DE" else "low"
            found.append(Finding("radon", f"CC-{b['rank']}", _rel(root, path), b["lineno"], "quality", severity,
                                 f"{b['name']} has cyclomatic complexity {b['complexity']}"))
    return found


def semgrep(root: Path) -> list[Finding]:
    exe = Path(sys.executable).with_name("semgrep")  # `python -m semgrep` is deprecated and prints nothing
    out = _run([str(exe), "scan", "--config", str(RULES), "--json", "--metrics=off",
                "--quiet", "--disable-version-check", str(root)])
    levels = {"ERROR": "high", "WARNING": "medium"}
    return [
        Finding("semgrep", r["check_id"].rsplit(".", 1)[-1], _rel(root, r["path"]), r["start"]["line"], "security",
                levels.get(r["extra"]["severity"], "low"), r["extra"]["message"])
        for r in json.loads(out or "{}").get("results", [])
    ]


def secrets(root: Path, max_bytes: int = 1_000_000) -> list[Finding]:
    from security.secrets import scan_text

    skip = set(SKIP_DIRS.split(","))
    found = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or skip & set(path.relative_to(root).parts) or path.stat().st_size > max_bytes:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for s in scan_text(text):
            found.append(Finding("secrets", s.rule, path.relative_to(root).as_posix(), s.line, "security", "high",
                                 f"hardcoded secret ({s.rule})"))
    return found


def injection(root: Path) -> list[Finding]:
    from security.injection import scan  # imports Finding from here

    return scan(root)


def analyze(root: str | Path) -> list[Finding]:
    root = Path(root).resolve()
    findings = [*ruff(root), *bandit(root), *radon(root), *semgrep(root), *secrets(root), *injection(root)]
    return sorted(findings, key=lambda f: (f.path, f.line, f.tool, f.rule))
