"""Does the v3 repair gain survive other wording, and does the model use test feedback? (2 x T4)

One vLLM server on GPU 0 serves the Qwen2.5-Coder-3B base with both adapters (run A: mixture v2,
run B: mixture v3, Kaggle dataset `locali-adapters-3b`). For each of the three models:

1. HumanEvalFix asked in two other ways (evaluation/tasks/humanevalpack.py):
   - humanevalfix_reworded: the same code and tests in wording no training prompt uses
   - humanevalfix_notests: the documented function only, no tests
2. repair with execution feedback (evaluation/feedback_repair.py), up to 3 attempts, plain errors
   and explained errors with sampled retries, as in experiments/results/feedback_t4

Model-written code runs in evaluation/isolated.py. Environment: PILOT=1 runs 8 problems.
"""

import json
import os
import subprocess
import sys
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
BASE = ("Qwen/Qwen2.5-Coder-3B-Instruct", "488639f1ff808d1d3d0ba301aef8c11461451ec5")
MODELS = {"base": "local", "mixv2": "mixv2", "mixv3": "mixv3"}  # result name: served model name
PORT = 8000
LIMIT = 8 if os.environ.get("PILOT") == "1" else None
FEEDBACK = {"plain": {"explain": False, "retry_temperature": 0.0},
            "explain-t06": {"explain": True, "retry_temperature": 0.6}}


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
    assert sh([sys.executable, "-m", "pip", "install", "-q", "datasets", "radon", "bandit"], setup_log) == 0
    if not (VLLM_VENV / "bin" / "python").exists():
        for step in (
            [sys.executable, "-m", "pip", "install", "-q", "uv"],
            [sys.executable, "-m", "uv", "venv", str(VLLM_VENV), "--python", "3.12"],
            [sys.executable, "-m", "uv", "pip", "install", "--python", str(VLLM_VENV / "bin" / "python"),
             f"vllm=={VLLM_VERSION}"],
        ):
            assert sh(step, setup_log) == 0, f"vllm install failed: {step}"
    sys.path.insert(0, str(CODE))
    import evaluation.rescore  # noqa: F401 - fail here, not after the server has started
    log("setup done")


def score_in_isolation() -> str:
    from evaluation import isolated
    from evaluation.tasks import codegen, humanevalpack

    def run_program(program: str, timeout_s: float = 60) -> codegen.Outcome:
        r = isolated.run_isolated(program, timeout_s=min(timeout_s, 60))
        return codegen.Outcome(r.passed, r.status, r.error or "", r.seconds)

    codegen.run_program = run_program
    humanevalpack.run_program = run_program
    return isolated.network_isolation()


def adapters() -> dict[str, Path]:
    found = {p.parent.name: p.parent for p in Path("/kaggle/input").rglob("adapter_config.json")}
    assert {"mixv2", "mixv3"} <= set(found), f"adapters not found: {found}"
    return {k: found[k] for k in ("mixv2", "mixv3")}


def wait_healthy(server: subprocess.Popen, timeout_s: float = 1800) -> bool:
    start = time.time()
    while time.time() - start < timeout_s:
        if server.poll() is not None:
            return False
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=5)
            return True
        except OSError:
            time.sleep(5)
    return False


def reworded(name: str, served: str) -> None:
    from evaluation.rescore import rescore_run
    from evaluation.run import TASKS

    for task_name in ("humanevalfix_reworded", "humanevalfix_notests"):
        out = RESULTS / task_name / name
        cmd = [sys.executable, "-m", "evaluation.run", "--benchmark", task_name, "--generate-only", "--workers", "16",
               "--model-id", f"qwen2.5-coder-3b-{name}", "--model-revision", BASE[1], "--quantization", "fp16",
               "--runtime", f"vLLM {VLLM_VERSION} T4 + LoRA", "--base-url", f"http://127.0.0.1:{PORT}/v1",
               "--served-model", served, "--out", str(out), "--notes", f"prompt robustness check, model {name}",
               *(["--limit", str(LIMIT)] if LIMIT else [])]
        rc = sh(cmd, LOGS / f"run_{task_name}_{name}.log", cwd=CODE)
        if rc != 0:
            log(f"{task_name}/{name}: FAILED rc={rc}")
            continue
        task = TASKS[task_name]
        summary = rescore_run(out, task, task.load(LIMIT), workers=8)
        log(f"{task_name}/{name}: pass@1 {summary['metrics']['pass@1']}")


def feedback(name: str, served: str, items) -> None:
    from evaluation.client import ChatClient
    from evaluation.feedback_repair import explain_asserts, repair_with_feedback
    from evaluation.isolated import run_isolated
    from evaluation.tasks.humanevalpack import _import_lines

    client = ChatClient(f"http://127.0.0.1:{PORT}/v1", model=served)
    for config, s in FEEDBACK.items():
        out = RESULTS / "feedback" / name / config
        out.mkdir(parents=True, exist_ok=True)

        def solve(item, s=s):
            def program(code):
                test = explain_asserts(item.test) if s["explain"] else item.test
                return f"{item.imports}\n{_import_lines(item.declaration)}\n{item.test_setup}\n\n{code}\n\n{test}\n"

            def run(code):
                r = run_isolated(program(code), timeout_s=30)
                return r.passed, (None if r.passed else r.error)

            model = lambda m: client.complete(m, max_tokens=768, seed=3407).text
            retry = (lambda m: client.complete(m, max_tokens=768, temperature=s["retry_temperature"], seed=3407).text
                     ) if s["retry_temperature"] else None
            return repair_with_feedback(item, model, run, 3, retry_model=retry) | {"bug_type": item.bug_type}

        start = time.time()
        with ThreadPoolExecutor(16) as pool:
            rows = list(pool.map(solve, items))
        (out / "samples.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        n = len(rows)
        within = {k: sum(r["fixed_at"] is not None and r["fixed_at"] <= k for r in rows) for k in (1, 2, 3)}
        summary = {"model": name, "config": config, **s, "n": n, "fixed_within": within,
                   "rate_within": {k: round(100 * v / n, 1) for k, v in within.items()},
                   "seconds": round(time.time() - start)}
        (out / "summary.json").write_text(json.dumps(summary, indent=1))
        log(f"feedback {name}/{config}: {summary['rate_within']}")


def main() -> None:
    setup()
    isolation = score_in_isolation()
    paths = adapters()
    log(f"adapters {paths}; network isolation {isolation}")
    cmd = [str(VLLM_VENV / "bin" / "vllm"), "serve", BASE[0], "--revision", BASE[1], "--served-model-name", "local",
           "--port", str(PORT), "--dtype", "half", "--max-model-len", "4096", "--gpu-memory-utilization", "0.90",
           "--enforce-eager", "--seed", "3407", "--enable-lora", "--max-lora-rank", "16", "--max-loras", "2",
           "--lora-modules", *(f"{k}={v}" for k, v in paths.items())]
    with open(LOGS / "vllm.log", "w") as fh:
        server = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"})
    try:
        if not wait_healthy(server):
            raise RuntimeError("server failed to start, see logs/vllm.log")
        log("server ready")
        from evaluation.tasks.humanevalpack import load_humanevalpack

        items = load_humanevalpack(LIMIT)
        for name, served in MODELS.items():
            reworded(name, served)
        for name, served in MODELS.items():
            feedback(name, served, items)
    finally:
        server.terminate()
        try:
            server.wait(timeout=120)
        except subprocess.TimeoutExpired:
            server.kill()
    log("all done")


if __name__ == "__main__":
    main()
