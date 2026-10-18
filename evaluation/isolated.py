"""Run one model-written Python program in an isolated process, where Docker is not available (Kaggle).

The laptop runs model code in the Docker sandbox (security/sandbox.py). Kaggle has no Docker but
runs jobs as root, so each program gets:

- no network: its own empty network namespace (`unshare --net`, root only)
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


def _last_error(stderr: str) -> str:
    lines = [line for line in stderr.strip().splitlines() if line.strip()]
    return lines[-1].strip() if lines else "the program failed"


def run_isolated(program: str, timeout_s: float = 60, memory_mb: int = 1024, isolate_network: bool = True) -> Result:
    folder = tempfile.mkdtemp(prefix="locali-run-")
    try:
        with open(os.path.join(folder, "candidate.py"), "w") as f:
            f.write(program)
        cmd = [sys.executable, "-I", "candidate.py"]
        # limits applied by prlimit rather than preexec_fn, which is unsafe when the caller uses threads
        cmd = ["prlimit", f"--as={memory_mb * 1024**2}", f"--cpu={int(timeout_s) + 5}",
               f"--fsize={50 * 1024**2}", "--nproc=256", "--", *cmd]
        if isolate_network:
            cmd = ["unshare", "--net", "--", *cmd]
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
