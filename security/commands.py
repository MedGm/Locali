"""The only way the assistant's runtime code starts another program.

Allowed: git and GNU patch (workspaces and patches), docker (the test sandbox), and the static
analysers Ruff, Bandit and Radon (as `python -m`) and Semgrep. Programs are named bare, so nothing can
point an allowed name at another binary by path. There is no shell mode. Anything else, such as
curl, sh -c, python -c or pip, raises CommandNotAllowed.

One program is started and left running: llama.cpp's server for the playground's comparison model
(`start_model_server`). Its path comes from the operator's settings, never from a request; the
command must be `<...>/llama-server -m <file>.gguf ...` and is refused otherwise.

A test checks that no other module of backend/, mcp_servers/ or security/ imports subprocess or
calls os.system / os.popen / os.exec* / os.spawn*.
"""

import subprocess
import sys
from pathlib import Path

PROGRAMS = {"git", "patch", "docker"}
PYTHON_MODULES = {"ruff", "bandit", "radon"}
SEMGREP = str(Path(sys.executable).with_name("semgrep"))
MODEL_SERVER = "llama-server"

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


def start_model_server(cmd: list[str], *, log: str | Path | None = None) -> subprocess.Popen:
    """Start llama.cpp's server and return the running process; its output goes to `log` or nowhere."""
    if not (len(cmd) > 2 and Path(cmd[0]).name == MODEL_SERVER and cmd[1] == "-m" and cmd[2].endswith(".gguf")):
        for hook in REFUSAL_HOOKS:
            hook(list(cmd))
        raise CommandNotAllowed(f"not a model server command: {cmd[:3]}")
    if log is None:
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    with Path(log).open("ab") as out:  # the child keeps its own copy of the file
        return subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT)
