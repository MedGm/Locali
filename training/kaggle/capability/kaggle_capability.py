"""Capability study, step 2 (T4): does the prompt's shape pick the style, and is the right program
still in the fine-tuned models?

One vLLM server: the base Qwen2.5-Coder-3B ("local") with the run D and run E adapters.

1. greedy: HumanEval+ and MBPP+, each in its own prompt shape and swapped (humaneval_plus_english,
   mbpp_plus_stub; evaluation/tasks/codegen.py), for all three models.
2. samples: 20 answers per HumanEval+ problem at temperature 0.8 (top-p 0.95), for all three.
3. logprobs: every model scores every model's greedy HumanEval+ answer (sum and per-token
   log-probability of the answer given the prompt): is the base's answer still likely under D/E?

Model-written code runs in evaluation/isolated.py. PILOT=1: 8 problems, 4 samples.
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
ADAPTERS = ("mixv3b-diag", "mixv3s")
MODELS = {"qwen2.5-coder-3b": "local", "qwen2.5-coder-3b-ft-qlora-mixv3b-diag": "mixv3b-diag",
          "qwen2.5-coder-3b-ft-qlora-mixv3s": "mixv3s"}  # model id: served name
GREEDY_TASKS = ("humaneval_plus", "humaneval_plus_english", "mbpp_plus", "mbpp_plus_stub")
PILOT = os.environ.get("PILOT") == "1"
LIMIT = 8 if PILOT else None
N_SAMPLES = 4 if PILOT else 20
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


def greedy() -> None:
    from evaluation.rescore import rescore_run
    from evaluation.run import TASKS

    for model_id, served in MODELS.items():
        for task_name in GREEDY_TASKS:
            out = RESULTS / task_name / f"{model_id}__fp16__kaggle-t4"
            cmd = [sys.executable, "-m", "evaluation.run", "--benchmark", task_name, "--generate-only",
                   "--workers", "16", "--model-id", model_id, "--model-revision", BASE[1], "--quantization", "fp16",
                   "--runtime", f"vLLM {VLLM_VERSION} T4" + (" + LoRA" if served != "local" else ""),
                   "--base-url", f"{URL}/v1", "--served-model", served, "--out", str(out),
                   "--notes", "capability study step 2", *(["--limit", str(LIMIT)] if LIMIT else [])]
            if sh(cmd, LOGS / f"greedy_{task_name}_{model_id}.log", cwd=CODE) != 0:
                log(f"greedy {task_name}/{model_id}: FAILED")
                continue
            task = TASKS[task_name]
            summary = rescore_run(out, task, task.load(LIMIT), workers=8)
            log(f"greedy {task_name}/{model_id}: pass@1 {summary['metrics']['pass@1']}")


def sample_model(model_id: str, served: str, task, items: list, out: Path) -> None:
    from evaluation.client import Completion

    def generate(item):
        body = {"model": served, "messages": task.messages(item), "n": N_SAMPLES, "temperature": 0.8,
                "top_p": 0.95, "max_tokens": 768, "seed": 3407}
        d = post("/v1/chat/completions", body)
        return item, [(c["message"]["content"], c["finish_reason"]) for c in d["choices"]]

    start = time.time()
    with ThreadPoolExecutor(max_workers=8) as pool:
        generated = list(pool.map(generate, items))
    log(f"samples {model_id}: generated in {time.time() - start:.0f}s")

    cache: dict[tuple[str, str], dict] = {}  # identical answers are run once

    def score(job):
        item, k, text, finish = job
        key = (item.task_id, text)
        if key not in cache:
            cache[key] = task.score(item, Completion(text, "", None, None, 0, 0, finish), 20)
        s = cache[key]
        return {"task_id": item.task_id, "k": k, "passed": s["passed"], "status": s["status"],
                "finish_reason": finish, "text": text}

    jobs = [(item, k, text, finish) for item, answers in generated for k, (text, finish) in enumerate(answers)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(score, jobs))
    with out.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    log(f"samples {model_id}: {sum(r['passed'] for r in rows)}/{len(rows)} passed, {time.time() - start:.0f}s")


def samples() -> None:
    from evaluation.run import TASKS

    task = TASKS["humaneval_plus"]
    items = task.load(LIMIT)
    out_dir = WORK / "samples"
    out_dir.mkdir(exist_ok=True)
    for model_id, served in MODELS.items():
        sample_model(model_id, served, task, items, out_dir / f"{model_id}.jsonl")


def logprobs() -> None:
    from evaluation.run import TASKS

    task = TASKS["humaneval_plus"]
    items = {i.task_id: i for i in task.load(LIMIT)}
    answers = {}
    for model_id in MODELS:
        path = RESULTS / "humaneval_plus" / f"{model_id}__fp16__kaggle-t4" / "samples.jsonl"
        answers[model_id] = {r["task_id"]: r["completion"] for r in map(json.loads, path.read_text().splitlines())}

    def one(job):
        model_id, source, task_id = job
        served = MODELS[model_id]
        prompt = post("/tokenize", {"model": served, "messages": task.messages(items[task_id]),
                                    "add_generation_prompt": True})["tokens"]
        answer = post("/tokenize", {"model": served, "prompt": answers[source][task_id],
                                    "add_special_tokens": False})["tokens"]
        d = post("/v1/completions", {"model": served, "prompt": prompt + answer, "max_tokens": 1,
                                     "temperature": 0.0, "prompt_logprobs": 0})
        scored = d["choices"][0]["prompt_logprobs"][len(prompt):]
        token_lp = [entry[str(tok)]["logprob"] for tok, entry in zip(answer, scored, strict=True)]
        return {"task_id": task_id, "model": model_id, "source": source, "n_tokens": len(answer),
                "sum_logprob": sum(token_lp), "token_logprobs": [round(x, 4) for x in token_lp]}

    jobs = [(m, s, t) for m in MODELS for s in MODELS for t in items if t in answers[s]]
    start = time.time()
    with ThreadPoolExecutor(max_workers=16) as pool:
        rows = list(pool.map(one, jobs))
    with (WORK / "logprobs.jsonl").open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    log(f"logprobs: {len(rows)} scored in {time.time() - start:.0f}s")


def main() -> None:
    setup()
    isolation = score_in_isolation()
    adapters = adapter_paths()
    log(f"adapters {adapters}; network isolation {isolation}")
    cmd = [str(VLLM_VENV / "bin" / "vllm"), "serve", BASE[0], "--revision", BASE[1], "--served-model-name", "local",
           "--port", str(PORT), "--dtype", "half", "--max-model-len", "4096", "--gpu-memory-utilization", "0.90",
           "--enforce-eager", "--seed", "3407", "--enable-lora", "--max-lora-rank", "16", "--max-loras", "2",
           "--max-logprobs", "1", "--lora-modules", *(f"{name}={path}" for name, path in adapters.items())]
    with open(LOGS / "vllm.log", "w") as fh:
        server = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"})
    try:
        if not wait_healthy(server):
            raise RuntimeError("server failed to start, see logs/vllm.log")
        log("server ready")
        greedy()
        logprobs()
        samples()
    finally:
        server.terminate()
        try:
            server.wait(timeout=120)
        except subprocess.TimeoutExpired:
            server.kill()
    log("all done")


if __name__ == "__main__":
    main()
