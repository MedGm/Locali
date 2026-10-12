"""Shared helpers for Kaggle GPU jobs: vLLM install, server lifecycle, power logging.

Jobs clone this repository at a pinned commit and import this module from the clone.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

VLLM_VERSION = "0.29.0"
VLLM_VENV = Path("/tmp/venv-vllm")
TEXT_ONLY = ["--limit-mm-per-prompt", '{"image": 0, "video": 0}']


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sh(cmd: list[str], logfile: Path, **kwargs) -> int:
    with open(logfile, "a") as fh:
        return subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, check=False, **kwargs).returncode


def install_vllm(logfile: Path) -> None:
    if (VLLM_VENV / "bin" / "python").exists():
        return
    py = str(VLLM_VENV / "bin" / "python")
    for step in (
        [sys.executable, "-m", "pip", "install", "-q", "uv"],
        [sys.executable, "-m", "uv", "venv", str(VLLM_VENV), "--python", "3.12"],
        [sys.executable, "-m", "uv", "pip", "install", "--python", py, f"vllm=={VLLM_VERSION}"],
    ):
        if sh(step, logfile) != 0:
            raise RuntimeError(f"vLLM install failed at: {' '.join(step)}")


def start_power_log(path: Path) -> subprocess.Popen:
    fh = open(path, "a")  # noqa: SIM115 - lives as long as the logger process
    return subprocess.Popen(
        ["nvidia-smi", "--query-gpu=timestamp,index,power.draw,memory.used",
         "--format=csv,noheader,nounits", "-lms", "1000"],
        stdout=fh, stderr=subprocess.DEVNULL,
    )


def start_server(repo: str, revision: str, gpus: list[int], port: int, logfile: Path,
                 extra: list[str] | None = None, max_model_len: int = 4096) -> subprocess.Popen:
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": ",".join(map(str, gpus))}
    cmd = [
        str(VLLM_VENV / "bin" / "vllm"), "serve", repo, "--revision", revision,
        "--served-model-name", "local", "--port", str(port), "--dtype", "half",
        "--max-model-len", str(max_model_len), "--gpu-memory-utilization", "0.90", "--enforce-eager",
        "--seed", "3407", "--tensor-parallel-size", str(len(gpus)), *(extra or []),
    ]
    with open(logfile, "w") as fh:
        return subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env)


def wait_healthy(port: int, server: subprocess.Popen, timeout_s: float = 1800) -> bool:
    start = time.time()
    while time.time() - start < timeout_s:
        if server.poll() is not None:
            return False
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5)
            return True
        except OSError:
            time.sleep(5)
    return False


def stop_server(server: subprocess.Popen) -> None:
    server.terminate()
    try:
        server.wait(timeout=120)
    except subprocess.TimeoutExpired:
        server.kill()


def chat(port: int, messages: list[dict], max_tokens: int, temperature: float = 0.0) -> dict:
    body = {
        "model": "local", "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
        "seed": 3407, "chat_template_kwargs": {"enable_thinking": False},
    }
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.load(response)


def run_requests(port: int, jobs: list[tuple[str, list[dict]]], out: Path, max_tokens: int, workers: int = 32) -> None:
    """Send (id, messages) jobs concurrently; append one JSON line per answer to `out`."""
    import threading

    lock = threading.Lock()

    def one(job: tuple[str, list[dict]]) -> None:
        job_id, messages = job
        try:
            d = chat(port, messages, max_tokens)
            row = {"id": job_id, "text": d["choices"][0]["message"]["content"],
                   "finish_reason": d["choices"][0]["finish_reason"],
                   "output_tokens": d["usage"]["completion_tokens"]}
        except Exception as e:
            row = {"id": job_id, "error": f"{type(e).__name__}: {e}"[:300]}
        with lock, out.open("a") as fh:
            fh.write(json.dumps(row) + "\n")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, jobs))
