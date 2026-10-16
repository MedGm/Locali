"""The only way the assistant's runtime code starts another program.

Allowed: git and GNU patch (workspaces and patches), docker (the test sandbox), and the static
analysers Ruff, Bandit and Radon (as `python -m`) and Semgrep. Programs are named bare, so nothing can
point an allowed name at another binary by path. There is no shell mode. Anything else, such as
curl, sh -c, python -c or pip, raises CommandNotAllowed.

A test checks that no other module of backend/, mcp_servers/ or security/ imports subprocess or
calls os.system / os.popen / os.exec* / os.spawn*.
"""

import subprocess
import sys
from pathlib import Path

PROGRAMS = {"git", "patch", "docker"}
PYTHON_MODULES = {"ruff", "bandit", "radon"}
SEMGREP = str(Path(sys.executable).with_name("semgrep"))

TimeoutExpired = subprocess.TimeoutExpired
CompletedProcess = subprocess.CompletedProcess


REFUSAL_HOOKS: list = []  # called with the refused command before raising (the API audits refusals)


class CommandNotAllowed(Exception):
    pass


def _allowed(cmd: list[str]) -> bool:
    if not cmd:
        return False
    if cmd[0] in PROGRAMS or cmd[0] == SEMGREP:
        return True
    return cmd[0] == sys.executable and len(cmd) > 2 and cmd[1] == "-m" and cmd[2] in PYTHON_MODULES


def run(cmd: list[str], *, input: str | None = None, cwd: str | Path | None = None,
        timeout: float | None = None, check: bool = False, text: bool = True) -> CompletedProcess:
    if not _allowed(cmd):
        for hook in REFUSAL_HOOKS:
            hook(list(cmd))
        raise CommandNotAllowed(f"not on the command allow-list: {cmd[:3]}")
    return subprocess.run(cmd, input=input, cwd=cwd, timeout=timeout, check=check, text=text,
                          capture_output=True)
