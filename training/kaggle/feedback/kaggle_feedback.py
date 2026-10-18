"""HumanEvalFix (Python) with execution feedback, base vs fine-tuned, on Kaggle (2 x T4).

Each model gets a vLLM server on its own GPU. For every problem the model answers, the answer runs
against the tests, and on failure the model sees the error and tries again, up to 3 attempts
(evaluation/feedback_repair.py). Configurations:

- plain: the error as the test gives it (often a bare AssertionError), greedy retries
- explain-t06: failing assertions say what the code returned and what was expected, and attempts
  2 and 3 are sampled at temperature 0.6

Model-written code runs on this VM in evaluation/isolated.py (no network, own folder, clean
environment, limits, timeout), not in the laptop's Docker sandbox. First the harness is checked:
every reference solution must pass and every buggy one fail, with the original and the explained
tests.

Environment: PILOT=1 runs 8 problems; CONFIGS=plain,explain-t06 and MODELS=ft,base pick what runs.
"""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = "https://github.com/MedGm/Locali.git"
COMMIT = "__LOCALI_COMMIT__"  # replaced when the notebook is built
WORK = Path("/kaggle/working")
CODE = Path("/tmp/locali")
VLLM_VENV = Path("/tmp/venv-vllm")
VLLM_VERSION = "0.29.0"
RESULTS = WORK / "results"
LOGS = WORK / "logs"
LIMIT = 8 if os.environ.get("PILOT") == "1" else None
CONFIGS = os.environ.get("CONFIGS", "plain,explain-t06").split(",")
SETTINGS = {"plain": {"explain": False, "retry_temperature": 0.0},
            "explain-t06": {"explain": True, "retry_temperature": 0.6}}
MODELS = {  # key: (repo, revision, gpus, port, extra vLLM flags)
    "ft": ("MedGm/Llama-Locali-Qwen2.5-Coder-1.5B", "a1b0b1189d2050dd20013371fc327362ea6b2964", "0", 8000, []),
    "base": ("Qwen/Qwen2.5-Coder-1.5B-Instruct", "2e1fd397ee46e1388853d2af2c993145b0f1098a", "1", 8001, []),
}
RUN_MODELS = os.environ.get("MODELS", "ft,base").split(",")


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
    assert sh([sys.executable, "-m", "pip", "install", "-q", "datasets"], setup_log) == 0
    if not (VLLM_VENV / "bin" / "python").exists():
        for step in (
            [sys.executable, "-m", "pip", "install", "-q", "uv"],
            [sys.executable, "-m", "uv", "venv", str(VLLM_VENV), "--python", "3.12"],
            [sys.executable, "-m", "uv", "pip", "install", "--python", str(VLLM_VENV / "bin" / "python"),
             f"vllm=={VLLM_VERSION}"],
        ):
            assert sh(step, setup_log) == 0, f"vllm install failed: {step}"
    sys.path.insert(0, str(CODE))
    log("setup done")


def program(item, code: str, explain: bool) -> str:
    from evaluation.feedback_repair import explain_asserts
    from evaluation.tasks.humanevalpack import _import_lines

    test = explain_asserts(item.test) if explain else item.test
    return f"{item.imports}\n{_import_lines(item.declaration)}\n{item.test_setup}\n\n{code}\n\n{test}\n"


def validate(items) -> dict:
    from evaluation.isolated import run_isolated

    report = {}
    for explain in (False, True):
        for which in ("canonical_solution", "buggy_solution"):
            def check(it, which=which, explain=explain):
                r = run_isolated(program(it, it.declaration + getattr(it, which), explain), timeout_s=30)
                return it.task_id, r.passed, r.error
            with ThreadPoolExecutor(8) as pool:
                rows = list(pool.map(check, items))
            key = f"{'explained' if explain else 'original'} tests, {which}"
            report[key] = {"passed": sum(p for _, p, _ in rows), "n": len(rows),
                           "unexpected": [(t, e) for t, p, e in rows if p != (which == "canonical_solution")][:10]}
            log(f"validation {key}: {report[key]['passed']}/{len(rows)} pass")
    (WORK / "validation.json").write_text(json.dumps(report, indent=1))
    return report


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


def run_model(key: str, items) -> None:
    from evaluation.client import ChatClient
    from evaluation.feedback_repair import repair_with_feedback
    from evaluation.isolated import run_isolated

    repo, revision, gpus, port, extra = MODELS[key]
    cmd = [str(VLLM_VENV / "bin" / "vllm"), "serve", repo, "--revision", revision, "--served-model-name", "local",
           "--port", str(port), "--dtype", "half", "--max-model-len", "4096", "--gpu-memory-utilization", "0.90",
           "--seed", "3407", "--tensor-parallel-size", str(len(gpus.split(","))), *extra]
    with open(LOGS / f"vllm_{key}.log", "w") as fh:
        server = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                  env={**os.environ, "CUDA_VISIBLE_DEVICES": gpus})
    try:
        if not wait_healthy(port, server):
            log(f"{key}: server failed to start")
            return
        client = ChatClient(f"http://127.0.0.1:{port}/v1")
        for config in CONFIGS:
            s = SETTINGS[config]
            out = RESULTS / key / config
            out.mkdir(parents=True, exist_ok=True)

            def solve(item, s=s):
                model = lambda m: client.complete(m, max_tokens=768, seed=3407).text
                retry = (lambda m: client.complete(m, max_tokens=768, temperature=s["retry_temperature"],
                                                   seed=3407).text) if s["retry_temperature"] else None

                def run(code):
                    r = run_isolated(program(item, code, s["explain"]), timeout_s=30)
                    return r.passed, (None if r.passed else r.error)

                return repair_with_feedback(item, model, run, 3, retry_model=retry) | {"bug_type": item.bug_type}

            start = time.time()
            with ThreadPoolExecutor(16) as pool:
                rows = list(pool.map(solve, items))
            (out / "samples.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            n = len(rows)
            within = {k: sum(r["fixed_at"] is not None and r["fixed_at"] <= k for r in rows) for k in (1, 2, 3)}
            summary = {"model": key, "config": config, **s, "n": n, "fixed_within": within,
                       "rate_within": {k: round(100 * v / n, 1) for k, v in within.items()},
                       "model_calls": sum(r["attempts"] for r in rows), "seconds": round(time.time() - start)}
            (out / "summary.json").write_text(json.dumps(summary, indent=1))
            log(f"{key}/{config}: {summary['rate_within']}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=120)
        except subprocess.TimeoutExpired:
            server.kill()


def main() -> None:
    setup()
    from evaluation.tasks.humanevalpack import load_humanevalpack

    items = load_humanevalpack(LIMIT)
    validate(items)
    threads = [threading.Thread(target=run_model, args=(k, items)) for k in RUN_MODELS]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    log("all done")


if __name__ == "__main__":
    main()
