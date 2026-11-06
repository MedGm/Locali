"""Generate answers for all benchmark tasks on Kaggle (2 x T4) with vLLM; score later locally.

Model code from the answers is never executed here: Kaggle has no Docker sandbox and has
internet access. Answers are scored on the laptop with `python -m evaluation.rescore`.

Each GPU works through its own model queue in parallel; a model runs as a vLLM OpenAI server and
the harness (`evaluation.run --generate-only`) sends 16 concurrent requests. `nvidia-smi` logs
board power every second; each run's GPU energy is integrated here, on the machine that wrote
the log, and stored in its summary.json.

Environment variables:
    LIMIT=3          items per task (pilot run); unset for full runs
    QUEUES=small     "small" (four 1.5-4.7B models, one queue per GPU) or "reference" (9B on both GPUs)
"""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

REPO = "https://github.com/MedGm/Locali.git"
COMMIT = "3431c53f73661b936d38d75d307f420ced5c3cd0"  # replaced when the notebook is built
WORK = Path("/kaggle/working")
CODE = Path("/tmp/locali")
VLLM_VENV = Path("/tmp/venv-vllm")
VLLM_VERSION = "0.29.0"
RESULTS = WORK / "results"
LOGS = WORK / "logs"
POWER_LOG = WORK / "gpu_power.csv"

TASKS = [
    "humaneval_plus", "mbpp_plus", "humanevalfix", "bugdetect", "cruxeval_o",
    "testgen", "refactor", "completion", "securecodegen", "vulndetect",
]
TEXT_ONLY = ["--limit-mm-per-prompt", '{"image": 0, "video": 0}']

MODELS = {
    "qwen2.5-coder-1.5b": {"repo": "Qwen/Qwen2.5-Coder-1.5B-Instruct",
                           "revision": "2e1fd397ee46e1388853d2af2c993145b0f1098a", "extra": []},
    "phi-4-mini": {"repo": "unsloth/Phi-4-mini-instruct",
                   "revision": "75becc471c56fc34761ec998615ca6f8535c5a61", "extra": []},
    "qwen3.5-2b": {"repo": "Qwen/Qwen3.5-2B",
                   "revision": "15852e8c16360a2fea060d615a32b45270f8a8fc", "extra": TEXT_ONLY},
    "qwen3.5-4b": {"repo": "Qwen/Qwen3.5-4B",
                   "revision": "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a", "extra": TEXT_ONLY},
    "qwen3.5-9b": {"repo": "Qwen/Qwen3.5-9B",
                   "revision": "c202236235762e1c871ad0ccb60c8ee5ba337b9a", "extra": TEXT_ONLY},
}
QUEUE_SETS = {
    # (gpus, port, models)
    "small": [([0], 8000, ["qwen2.5-coder-1.5b", "phi-4-mini"]),
              ([1], 8001, ["qwen3.5-2b", "qwen3.5-4b"])],
    "reference": [([0, 1], 8000, ["qwen3.5-9b"])],
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sh(cmd: list[str], logfile: Path, **kwargs) -> int:
    with open(logfile, "a") as fh:
        return subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, check=False, **kwargs).returncode


def setup() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    setup_log = LOGS / "setup.log"
    if not CODE.exists():
        assert sh(["git", "clone", REPO, str(CODE)], setup_log) == 0, "clone failed"
    assert sh(["git", "-C", str(CODE), "checkout", COMMIT], setup_log) == 0, "checkout failed"
    # Harness dependencies (the harness only needs these to generate; scoring happens locally).
    assert sh([sys.executable, "-m", "pip", "install", "-q", "radon", "bandit", "datasets"], setup_log) == 0
    if not (VLLM_VENV / "bin" / "python").exists():
        steps = [
            [sys.executable, "-m", "pip", "install", "-q", "uv"],
            [sys.executable, "-m", "uv", "venv", str(VLLM_VENV), "--python", "3.12"],
            [sys.executable, "-m", "uv", "pip", "install", "--python", str(VLLM_VENV / "bin" / "python"),
             f"vllm=={VLLM_VERSION}"],
        ]
        for step in steps:
            assert sh(step, setup_log) == 0, f"vllm install failed: {step}"
    log("setup done")


def start_power_log() -> subprocess.Popen:
    fh = open(POWER_LOG, "a")  # noqa: SIM115 - lives as long as the logger process
    return subprocess.Popen(
        ["nvidia-smi", "--query-gpu=timestamp,index,power.draw,memory.used",
         "--format=csv,noheader,nounits", "-lms", "1000"],
        stdout=fh, stderr=subprocess.DEVNULL,
    )


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


def run_model(model_id: str, gpus: list[int], port: int, limit: str | None) -> None:
    spec = MODELS[model_id]
    server_log = LOGS / f"vllm_{model_id}.log"
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": ",".join(map(str, gpus))}
    cmd = [
        str(VLLM_VENV / "bin" / "vllm"), "serve", spec["repo"], "--revision", spec["revision"],
        "--served-model-name", "local", "--port", str(port), "--dtype", "half",
        "--max-model-len", "4096", "--gpu-memory-utilization", "0.90", "--enforce-eager",
        "--seed", "3407", "--tensor-parallel-size", str(len(gpus)), *spec["extra"],
    ]
    log(f"{model_id}: starting vLLM on GPU {gpus}")
    with open(server_log, "w") as fh:
        server = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env)
    try:
        if not wait_healthy(port, server):
            log(f"{model_id}: server failed to start, see {server_log.name}")
            return
        log(f"{model_id}: server ready")
        for task in TASKS:
            out = RESULTS / task / f"{model_id}__fp16__kaggle-t4"
            run_cmd = [
                sys.executable, "-m", "evaluation.run", "--benchmark", task, "--generate-only",
                "--workers", "16", "--model-id", model_id, "--model-revision", spec["revision"],
                "--quantization", "fp16", "--runtime", f"vLLM {VLLM_VERSION} T4x{len(gpus)} eager",
                "--base-url", f"http://127.0.0.1:{port}/v1", "--out", str(out),
                "--notes", "Kaggle generate-only; scored locally in Docker sandbox",
            ]
            if limit:
                run_cmd += ["--limit", limit]
            start = time.time()
            rc = sh(run_cmd, LOGS / f"run_{model_id}.log", cwd=CODE)
            end = time.time()
            if rc != 0 or not (out / "summary.json").exists():
                log(f"{model_id}/{task}: FAILED rc={rc}")
                continue
            sys.path.insert(0, str(CODE))
            from evaluation.gpu_energy import attach_gpu_energy

            energy = attach_gpu_energy(out, POWER_LOG.read_text(), gpus, start, end)
            n = json.loads((out / "summary.json").read_text())["metrics"]["n"]
            log(f"{model_id}/{task}: {n} answers in {end - start:.0f}s, GPU energy {energy['total_j']} J")
    finally:
        server.terminate()
        try:
            server.wait(timeout=120)
        except subprocess.TimeoutExpired:
            server.kill()
        log(f"{model_id}: server stopped")


def main() -> None:
    limit = os.environ.get("LIMIT")
    queues = QUEUE_SETS[os.environ.get("QUEUES", "small")]
    setup()
    power = start_power_log()
    threads = [
        threading.Thread(target=lambda g=gpus, p=port, ms=models: [run_model(m, g, p, limit) for m in ms])
        for gpus, port, models in queues
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    power.terminate()
    log("all queues done")


if __name__ == "__main__":
    main()
