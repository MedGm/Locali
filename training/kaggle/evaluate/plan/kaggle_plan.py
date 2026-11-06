"""Do the fine-tuned models lose HumanEval+ because they answer with bare code? (T4)

The base Qwen2.5-Coder-3B explains before coding (about 240 output tokens on HumanEval+); every
fine-tuned run answers with bare code (about 90) and scores 8 points lower. If the missing
explanation is the cause, asking for a short plan before the code should close most of the gap.

One vLLM server serves the base with the run D adapter (`mixv3b-diag`, Kaggle dataset
`locali-adapters-3b`). Both models answer HumanEval+ twice on the same server: the standard
prompt and the plan-first prompt (evaluation/tasks/codegen.py, humaneval_plus_plan). Greedy.

Model-written code runs in evaluation/isolated.py. Environment: PILOT=1 runs 8 problems; ADAPTER,
MODEL_ID and TASKS (space-separated) evaluate another adapter on other tasks; BASE_TOO=0 skips the base.
"""

import os
import subprocess
import sys
import time
import urllib.request
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
ADAPTER = os.environ.get("ADAPTER", "mixv3b-diag")
MODELS = {"qwen2.5-coder-3b": "local"} if os.environ.get("BASE_TOO", "1") == "1" else {}  # model id: served name
MODELS[os.environ.get("MODEL_ID", f"qwen2.5-coder-3b-ft-qlora-{ADAPTER}")] = ADAPTER
TASKS = tuple(os.environ.get("TASKS", "humaneval_plus_plan humaneval_plus").split())
PORT = 8000
LIMIT = 8 if os.environ.get("PILOT") == "1" else None


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
    from evaluation.run import TASKS as REGISTERED

    assert set(TASKS) <= set(REGISTERED), f"unknown tasks: {set(TASKS) - set(REGISTERED)}"
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


def adapter_path() -> Path:
    found = {p.parent.name: p.parent for p in Path("/kaggle/input").rglob("adapter_config.json")}
    assert ADAPTER in found, f"adapter not found: {found}"
    return found[ADAPTER]


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


def evaluate(model_id: str, served: str) -> None:
    from evaluation.rescore import rescore_run
    from evaluation.run import TASKS as REGISTERED

    for task_name in TASKS:
        out = RESULTS / task_name / f"{model_id}__fp16__kaggle-t4"
        cmd = [sys.executable, "-m", "evaluation.run", "--benchmark", task_name, "--generate-only", "--workers", "16",
               "--model-id", model_id, "--model-revision", BASE[1], "--quantization", "fp16", "--max-tokens", "1024",
               "--runtime", f"vLLM {VLLM_VERSION} T4" + (" + LoRA" if served != "local" else ""),
               "--base-url", f"http://127.0.0.1:{PORT}/v1", "--served-model", served, "--out", str(out),
               "--notes", "plan-before-code check", *(["--limit", str(LIMIT)] if LIMIT else [])]
        rc = sh(cmd, LOGS / f"run_{task_name}_{model_id}.log", cwd=CODE)
        if rc != 0:
            log(f"{task_name}/{model_id}: FAILED rc={rc}")
            continue
        task = REGISTERED[task_name]
        summary = rescore_run(out, task, task.load(LIMIT), workers=8)
        log(f"{task_name}/{model_id}: pass@1 {summary['metrics']['pass@1']}")


def main() -> None:
    setup()
    isolation = score_in_isolation()
    adapter = adapter_path()
    log(f"adapter {adapter}; network isolation {isolation}")
    cmd = [str(VLLM_VENV / "bin" / "vllm"), "serve", BASE[0], "--revision", BASE[1], "--served-model-name", "local",
           "--port", str(PORT), "--dtype", "half", "--max-model-len", "4096", "--gpu-memory-utilization", "0.90",
           "--enforce-eager", "--seed", "3407", "--enable-lora", "--max-lora-rank", "16", "--max-loras", "1",
           "--lora-modules", f"{ADAPTER}={adapter}"]
    with open(LOGS / "vllm.log", "w") as fh:
        server = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"})
    try:
        if not wait_healthy(server):
            raise RuntimeError("server failed to start, see logs/vllm.log")
        log("server ready")
        for model_id, served in MODELS.items():
            evaluate(model_id, served)
    finally:
        server.terminate()
        try:
            server.wait(timeout=120)
        except subprocess.TimeoutExpired:
            server.kill()
    log("all done")


if __name__ == "__main__":
    main()
