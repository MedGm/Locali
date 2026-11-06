"""Capability study, step 4 (T4): does making the fine-tuned models spell out their code win back
HumanEval+?

Step 3 found that a fine-tuned model's wrong answer is one or two tokens from a right one, and that
those tokens are where the base writes a step comment, a setup variable or a helper and the
fine-tuned model a one-liner. Earlier prompts asking for a prose plan (experiments/results/3_finetune_3b/plan_t4)
or for the docstring (keepdoc_t4) did not close the gap. This job tests comments inside the code:

- standard: the usual HumanEval+ prompt;
- comments: the prompt asks for a short comment before each step (humaneval_plus_comments);
- scaffold: the usual prompt, and the answer is started for the model: its code fence, the stub
  (signature and docstring) and "    #", so the body has to open with a comment.

Each for the base and the run D and E adapters, greedy, with vLLM's default repetition penalty from
the model's generation_config (1.05, as in steps 2 and 3) and without it (1.0). Model-written code
runs in evaluation/isolated.py. PILOT=1: 8 problems.
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
LOGS = WORK / "logs"
BASE = ("Qwen/Qwen2.5-Coder-3B-Instruct", "488639f1ff808d1d3d0ba301aef8c11461451ec5")
ADAPTERS = ("mixv3b-diag", "mixv3s")
MODELS = {"qwen2.5-coder-3b": "local", "qwen2.5-coder-3b-ft-qlora-mixv3b-diag": "mixv3b-diag",
          "qwen2.5-coder-3b-ft-qlora-mixv3s": "mixv3s"}  # model id: served name
CONDITIONS = ("standard", "comments", "scaffold")
PENALTIES = (1.05, 1.0)
FENCES = {"qwen2.5-coder-3b": "```\npython\n"}  # how each model opens its answers (step 3)
FENCE = "```python\n"
PILOT = os.environ.get("PILOT") == "1"
LIMIT = 8 if PILOT else None
PORT = 8000
URL = f"http://127.0.0.1:{PORT}"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sh(cmd: list[str], logfile: Path, **kwargs) -> int:
    with open(logfile, "a") as fh:
        return subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, check=False, **kwargs).returncode


def post(path: str, body: dict, timeout: float = 600) -> dict:
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def setup() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
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
    import evaluation.tasks.codegen  # noqa: F401 - fail here, not after the server has started
    log("setup done")


def score_in_isolation() -> str:
    from evaluation import isolated
    from evaluation.tasks import codegen

    def run_program(program: str, timeout_s: float = 60) -> codegen.Outcome:
        r = isolated.run_isolated(program, timeout_s=min(timeout_s, 60))
        return codegen.Outcome(r.passed, r.status, r.error or "", r.seconds)

    codegen.run_program = run_program
    return isolated.network_isolation()


def adapter_paths() -> dict[str, Path]:
    found = {p.parent.name: p.parent for p in Path("/kaggle/input").rglob("adapter_config.json")}
    missing = set(ADAPTERS) - set(found)
    assert not missing, f"adapters not found: {missing}; have {sorted(found)}"
    return {name: found[name] for name in ADAPTERS}


def wait_healthy(server: subprocess.Popen, timeout_s: float = 1800) -> bool:
    start = time.time()
    while time.time() - start < timeout_s:
        if server.poll() is not None:
            return False
        try:
            urllib.request.urlopen(f"{URL}/health", timeout=5)
            return True
        except OSError:
            time.sleep(5)
    return False


def run_condition(model_id: str, condition: str, penalty: float, items: list) -> list[dict]:
    from evaluation.client import Completion
    from evaluation.run import TASKS
    from evaluation.tasks.codegen import scaffold_prefix

    served = MODELS[model_id]
    task = TASKS["humaneval_plus_comments" if condition == "comments" else "humaneval_plus"]

    def one(item):
        prompt = post("/tokenize", {"model": served, "messages": task.messages(item),
                                    "add_generation_prompt": True})["tokens"]
        prefix = scaffold_prefix(item, FENCES.get(model_id, FENCE)) if condition == "scaffold" else ""
        forced = post("/tokenize", {"model": served, "prompt": prefix, "add_special_tokens": False})["tokens"] if prefix else []
        d = post("/v1/completions", {"model": served, "prompt": prompt + forced, "max_tokens": 1024,
                                     "temperature": 0.0, "repetition_penalty": penalty})
        choice = d["choices"][0]
        text = prefix + choice["text"]
        s = task.score(item, Completion(text, "", None, None, 0, 0, choice["finish_reason"]), 20)
        return {"task_id": item.task_id, "model": model_id, "condition": condition, "penalty": penalty,
                "passed": s["passed"], "status": s["status"], "finish_reason": choice["finish_reason"],
                "output_tokens": d["usage"]["completion_tokens"], "code": s["code"], "text": text}

    with ThreadPoolExecutor(max_workers=16) as pool:
        return list(pool.map(one, items))


def conditions() -> None:
    from evaluation.run import TASKS

    items = TASKS["humaneval_plus"].load(LIMIT)
    out = WORK / "answers.jsonl"
    with out.open("w") as fh:
        for model_id in MODELS:
            for penalty in PENALTIES:
                for condition in CONDITIONS:
                    start = time.time()
                    rows = run_condition(model_id, condition, penalty, items)
                    for r in rows:
                        fh.write(json.dumps(r) + "\n")
                    fh.flush()
                    log(f"{model_id} {condition} penalty {penalty}: {sum(r['passed'] for r in rows)}/{len(rows)} "
                        f"in {time.time() - start:.0f}s")


def main() -> None:
    setup()
    isolation = score_in_isolation()
    adapters = adapter_paths()
    log(f"adapters {adapters}; network isolation {isolation}")
    cmd = [str(VLLM_VENV / "bin" / "vllm"), "serve", BASE[0], "--revision", BASE[1], "--served-model-name", "local",
           "--port", str(PORT), "--dtype", "half", "--max-model-len", "4096", "--gpu-memory-utilization", "0.90",
           "--enforce-eager", "--seed", "3407", "--enable-lora", "--max-lora-rank", "16", "--max-loras", "2",
           "--lora-modules", *(f"{name}={path}" for name, path in adapters.items())]
    with open(LOGS / "vllm.log", "w") as fh:
        server = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"})
    try:
        if not wait_healthy(server):
            raise RuntimeError("server failed to start, see logs/vllm.log")
        log("server ready")
        conditions()
    finally:
        server.terminate()
        try:
            server.wait(timeout=120)
        except subprocess.TimeoutExpired:
            server.kill()
    log("all done")


if __name__ == "__main__":
    main()
