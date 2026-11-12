"""Does a weaker or a merged adapter keep the repair gain and lose less code writing? (T4)

Every fine-tuned 3B run fixes more bugs than the base (HumanEvalFix 50 -> 62-63 %) and writes
code a little worse (HumanEval+ 81 -> 72-75 %). Two things that need no training:

- scale run E's adapter: the change it makes to each weight times 0.5 and 0.75;
- average run D and run E (D repairs better on the laptop, E explains and writes code better).

The variants are built here from the adapters in the Kaggle dataset `locali-adapters-3b`
(training/adapter_math.py) and served by one vLLM server next to the unchanged run E adapter, which
is the control: it must reproduce run E's scores. Greedy, same prompts as every other run.

Model-written code runs in evaluation/isolated.py. Environment: PILOT=1 runs 8 problems; TASKS
(space-separated) and SCALES (e.g. "0.5 0.75") change what is run; AVERAGE=0 leaves the D/E average out.

The second step registered in docs/preregistration-runs-fg.md (the chosen variant on test generation
and ConDefects, next to the same control) is this job with TASKS="testgen condefects": those answers
are only generated here and scored on the laptop, like every other run of the two.
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = "https://github.com/MedGm/Locali.git"
COMMIT = "cfcdff83d85259845ba9b9ff93b1cf0741c4b126"  # replaced when the notebook is built
WORK = Path("/kaggle/working")
CODE = Path("/tmp/locali")
VLLM_VENV = Path("/tmp/venv-vllm")
VLLM_VERSION = "0.29.0"
RESULTS = WORK / "results"
LOGS = WORK / "logs"
BASE = ("Qwen/Qwen2.5-Coder-3B-Instruct", "488639f1ff808d1d3d0ba301aef8c11461451ec5")
RUN_D, RUN_E = "mixv3b-diag", "mixv3s"
SCALES = tuple(float(x) for x in os.environ.get("SCALES", "0.5 0.75").split())
VARIANTS = WORK / "adapters"
TASKS = tuple(os.environ.get("TASKS", "humaneval_plus humanevalfix mbpp_plus").split())
AVERAGE = os.environ.get("AVERAGE", "1") == "1"
SCORED_HERE = {"humaneval_plus", "humanevalfix", "mbpp_plus"}
MAX_TOKENS = {"testgen": 768}  # as in the fine-tuning job; 1,024 everywhere else
CONDEFECTS_ITEMS = "experiments/results/4_final_checks/condefects/items.jsonl"
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

    unknown = set(TASKS) - set(REGISTERED) - {"condefects"}
    assert not unknown, f"unknown tasks: {unknown}"
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


def build_variants() -> dict[str, Path]:
    """served name -> adapter folder: run E unchanged, run E scaled, and the D/E average."""
    import json
    import shutil

    from safetensors.numpy import load_file, save_file

    from training.adapter_math import average, averaged_config, scale

    found = {p.parent.name: p.parent for p in Path("/kaggle/input").rglob("adapter_config.json")}
    assert {RUN_D, RUN_E} <= set(found), f"adapters not found: {sorted(found)}"
    state = {name: load_file(found[name] / "adapter_model.safetensors") for name in (RUN_D, RUN_E)}
    config = json.loads((found[RUN_E] / "adapter_config.json").read_text())
    built = {"e-x1.0": (state[RUN_E], config)}
    for factor in SCALES:
        built[f"e-x{factor}"] = (scale(state[RUN_E], factor), config)
    if AVERAGE:
        built["avg-d-e"] = (average(state[RUN_D], state[RUN_E]), averaged_config(config))
    paths = {}
    for name, (tensors, cfg) in built.items():
        out = VARIANTS / name
        out.mkdir(parents=True, exist_ok=True)
        save_file({k: v.astype("float32") for k, v in tensors.items()}, str(out / "adapter_model.safetensors"))
        (out / "adapter_config.json").write_text(json.dumps(cfg, indent=2))
        for extra in ("tokenizer.json", "tokenizer_config.json", "chat_template.jinja"):
            if (found[RUN_E] / extra).exists():
                shutil.copy(found[RUN_E] / extra, out / extra)
        paths[name] = out
    return paths


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


def condefects(model_id: str, served: str) -> None:
    """The 382 real bugs, asked as in the pre-registered check (training/kaggle/evaluate/repair_prereg)."""
    from evaluation.client import ChatClient
    from evaluation.run import RunConfig, run_benchmark, two_step
    from evaluation.tasks.condefects import ConDefectsTask

    task = ConDefectsTask(CODE / CONDEFECTS_ITEMS)
    client = ChatClient(f"http://127.0.0.1:{PORT}/v1", model=served)

    def call(messages):
        return client.complete(messages, max_tokens=1024, temperature=0.0, seed=3407)

    config = RunConfig(benchmark="condefects", model_id=model_id, runtime="vllm", max_tokens=1024,
                       base_url=f"http://127.0.0.1:{PORT}/v1", workers=16, dataset=task.dataset[0],
                       dataset_revision=task.dataset[1], generate_only=True, limit=LIMIT,
                       notes="kaggle T4, vLLM 0.29; adapter scaling, second step")
    summary = run_benchmark(config, task, task.load(LIMIT), lambda item: two_step(task, item, call),
                            RESULTS / "condefects" / model_id)
    log(f"condefects/{model_id}: {summary['metrics']['n']} answers")


def evaluate(model_id: str, served: str) -> None:
    from evaluation.rescore import rescore_run
    from evaluation.run import TASKS as REGISTERED

    for task_name in TASKS:
        if task_name == "condefects":
            condefects(model_id, served)
            continue
        out = RESULTS / task_name / f"{model_id}__fp16__kaggle-t4"
        cmd = [sys.executable, "-m", "evaluation.run", "--benchmark", task_name, "--generate-only", "--workers", "16",
               "--model-id", model_id, "--model-revision", BASE[1], "--quantization", "fp16", "--max-tokens", str(MAX_TOKENS.get(task_name, 1024)),
               "--runtime", f"vLLM {VLLM_VERSION} T4 + LoRA",
               "--base-url", f"http://127.0.0.1:{PORT}/v1", "--served-model", served, "--out", str(out),
               "--notes", "adapter scaling and D/E average", *(["--limit", str(LIMIT)] if LIMIT else [])]
        rc = sh(cmd, LOGS / f"run_{task_name}_{model_id}.log", cwd=CODE)
        if rc != 0:
            log(f"{task_name}/{model_id}: FAILED rc={rc}")
            continue
        if task_name not in SCORED_HERE:
            log(f"{task_name}/{model_id}: answers written, scored on the laptop")
            continue
        task = REGISTERED[task_name]
        summary = rescore_run(out, task, task.load(LIMIT), workers=8)
        log(f"{task_name}/{model_id}: pass@1 {summary['metrics']['pass@1']}")


def main() -> None:
    setup()
    isolation = score_in_isolation()
    variants = build_variants()
    log(f"variants {sorted(variants)}; network isolation {isolation}")
    cmd = [str(VLLM_VENV / "bin" / "vllm"), "serve", BASE[0], "--revision", BASE[1], "--served-model-name", "local",
           "--port", str(PORT), "--dtype", "half", "--max-model-len", "16384" if "condefects" in TASKS else "4096", "--gpu-memory-utilization", "0.90",
           "--enforce-eager", "--seed", "3407", "--enable-lora", "--max-lora-rank", "32", "--max-loras", "1",
           "--lora-modules", *(f"{name}={path}" for name, path in variants.items())]
    with open(LOGS / "vllm.log", "w") as fh:
        server = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"})
    try:
        if not wait_healthy(server):
            raise RuntimeError("server failed to start, see logs/vllm.log")
        log("server ready")
        for name in variants:
            evaluate(f"qwen2.5-coder-3b-ft-qlora-{name}", name)
    finally:
        server.terminate()
        try:
            server.wait(timeout=120)
        except subprocess.TimeoutExpired:
            server.kill()
    log("all done")


if __name__ == "__main__":
    main()
