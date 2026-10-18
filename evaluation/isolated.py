"""Run one model-written Python program in an isolated process, where Docker is not available (Kaggle).

The laptop runs model code in the Docker sandbox (security/sandbox.py). Kaggle has no Docker but
runs jobs as root, so each program gets:

- no network: its own empty network namespace (`unshare -rn`) where the machine allows it, else a
  guard at the top of the program that disables sockets (Kaggle's container refuses namespaces);
  network_isolation() says which one is in use
- an empty temporary folder as working directory, removed afterwards
- a clean environment (no tokens or keys inherited), Python in isolated mode (-I)
- limits on memory, CPU time, processes and file size, and a wall-clock timeout

It is a weaker boundary than the container (same filesystem, same user), which is why it is only
used on disposable Kaggle VMs that hold no secrets.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass


@dataclass
class Result:
    passed: bool
    status: str  # passed | failed | timeout
    error: str
    seconds: float


_GUARD = (
    "import socket as _locali_socket\n"
    "def _locali_no_network(*args, **kwargs):\n"
    "    raise OSError('network disabled in the Locali runner')\n"
    "_locali_socket.socket = _locali_no_network\n"
    "_locali_socket.create_connection = _locali_no_network\n"
    "_locali_socket.getaddrinfo = _locali_no_network\n"
    "del _locali_socket, _locali_no_network\n"
)
_MODE: str | None = None


def network_isolation() -> str:
    """'namespace' if an unprivileged network namespace can be made here, else 'guard'."""
    global _MODE
    if _MODE is None:
        try:
            ok = subprocess.run(["unshare", "-rn", "true"], capture_output=True, timeout=10, check=False).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            ok = False
        _MODE = "namespace" if ok else "guard"
    return _MODE


def _last_error(stderr: str) -> str:
    lines = [line for line in stderr.strip().splitlines() if line.strip()]
    return lines[-1].strip() if lines else "the program failed"


def run_isolated(program: str, timeout_s: float = 60, memory_mb: int = 1024, isolate_network: str = "auto") -> Result:
    """isolate_network: "auto" (the best available), "namespace", "guard" or "none"."""
    mode = network_isolation() if isolate_network == "auto" else isolate_network
    if mode == "guard":
        program = _GUARD + program
    folder = tempfile.mkdtemp(prefix="locali-run-")
    try:
        with open(os.path.join(folder, "candidate.py"), "w") as f:
            f.write(program)
        cmd = [sys.executable, "-I", "candidate.py"]
        # limits applied by prlimit rather than preexec_fn, which is unsafe when the caller uses threads
        cmd = ["prlimit", f"--as={memory_mb * 1024**2}", f"--cpu={int(timeout_s) + 5}",
               f"--fsize={50 * 1024**2}", "--nproc=256", "--", *cmd]
        if mode == "namespace":
            cmd = ["unshare", "-rn", "--", *cmd]
        env = {"PATH": "/usr/bin:/bin", "HOME": folder, "LANG": "C.UTF-8"}
        start = time.perf_counter()
        proc = subprocess.Popen(cmd, cwd=folder, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                text=True, start_new_session=True)  # its own group: a timeout kills all of it
        try:
            _, stderr = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, 9)
            proc.communicate()
            return Result(False, "timeout", f"the tests timed out after {timeout_s:.0f} s",
                          round(time.perf_counter() - start, 2))
        seconds = round(time.perf_counter() - start, 2)
        if proc.returncode == 0:
            return Result(True, "passed", "", seconds)
        return Result(False, "failed", _last_error(stderr)[:1500], seconds)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
