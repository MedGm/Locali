"""Pre-registered check, part 1 (docs/preregistration-repair.md): repair of real bugs.

Generates answers for ConDefects (Python, contests from 2024-02-01, harness-checked programs in
experiments/results/4_final_checks/condefects/items.jsonl) and QuixBugs (experiments/results/4_final_checks/quixbugs/items.jsonl)
with the registered prompt, greedy, at most 1,024 output tokens, vLLM's generation_config defaults
as in every other Kaggle run. Models: the 3B base with runs C, D and E on GPU 0, the 1.5B QLoRA v2
and the 1.5B base on GPU 1. This job only generates; scoring is in the local Docker sandbox.

PILOT=1: only the three format-check programs from before 2023
(experiments/results/4_final_checks/condefects/format_check.jsonl), to check that prompts are well formed and
answers can be extracted. Those answers are not scored.
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
COMMIT = "b8024fa60eedf467de90d602b2149d991ee0321b"  # replaced when the notebook is built
WORK = Path("/kaggle/working")
CODE = Path("/tmp/locali")
VLLM_VENV = Path("/tmp/venv-vllm")
VLLM_VERSION = "0.29.0"
RESULTS = WORK / "results"
LOGS = WORK / "logs"
PILOT = os.environ.get("PILOT") == "1"
MAX_TOKENS = 1024
BENCHMARKS = {"condefects": "experiments/results/4_final_checks/condefects/format_check.jsonl" if os.environ.get("PILOT") == "1"
              else "experiments/results/4_final_checks/condefects/items.jsonl",
              "quixbugs": None if os.environ.get("PILOT") == "1" else "experiments/results/4_final_checks/quixbugs/items.jsonl"}
ADAPTERS = ("mixv3b", "mixv3b-diag", "mixv3s")
SERVERS = {  # name: (repo, revision, gpu, port, memory share)
    "3b": ("Qwen/Qwen2.5-Coder-3B-Instruct", "488639f1ff808d1d3d0ba301aef8c11461451ec5", 0, 8000, 0.90),
    "1.5b-ft": ("MedGm/Llama-Locali-Qwen2.5-Coder-1.5B", "a1b0b1189d2050dd20013371fc327362ea6b2964", 1, 8001, 0.90),
    "1.5b": ("Qwen/Qwen2.5-Coder-1.5B-Instruct", "2e1fd397ee46e1388853d2af2c993145b0f1098a", 1, 8002, 0.90),
}
MODELS = {  # model id: (server, served name)
    "qwen2.5-coder-3b": ("3b", "local"),
    "qwen2.5-coder-3b-ft-qlora-mixv3b": ("3b", "mixv3b"),
    "qwen2.5-coder-3b-ft-qlora-mixv3b-diag": ("3b", "mixv3b-diag"),
    "qwen2.5-coder-3b-ft-qlora-mixv3s": ("3b", "mixv3s"),
    "qwen2.5-coder-1.5b-ft-qlora-v2": ("1.5b-ft", "local"),
    "qwen2.5-coder-1.5b": ("1.5b", "local"),
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sh(cmd: list[str], logfile: Path, **kwargs) -> int:
    with open(logfile, "a") as fh:
        return subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, check=False, **kwargs).returncode


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
    import evaluation.run  # noqa: F401 - fail here, not after the servers have started
    log("setup done")


def adapter_paths() -> dict[str, Path]:
    found = {p.parent.name: p.parent for p in Path("/kaggle/input").rglob("adapter_config.json")}
    missing = set(ADAPTERS) - set(found)
    assert not missing, f"adapters not found: {missing}; have {sorted(found)}"
    return {name: found[name] for name in ADAPTERS}


def start(name: str, adapters: dict[str, Path]) -> subprocess.Popen:
    repo, revision, gpu, port, share = SERVERS[name]
    cmd = [str(VLLM_VENV / "bin" / "vllm"), "serve", repo, "--revision", revision, "--served-model-name", "local",
           "--port", str(port), "--dtype", "half", "--max-model-len", "8192", "--gpu-memory-utilization", str(share),
           "--enforce-eager", "--seed", "3407"]
    if name == "3b" and adapters:
        cmd += ["--enable-lora", "--max-lora-rank", "16", "--max-loras", "3",
                "--lora-modules", *(f"{n}={p}" for n, p in adapters.items())]
    fh = open(LOGS / f"vllm-{name}.log", "w")  # noqa: SIM115 - stays open while the server runs
    return subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env={**os.environ, "CUDA_VISIBLE_DEVICES": str(gpu)})


def wait_healthy(port: int, server: subprocess.Popen, timeout_s: float = 1800) -> bool:
    begin = time.time()
    while time.time() - begin < timeout_s:
        if server.poll() is not None:
            return False
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5)
            return True
        except OSError:
            time.sleep(5)
    return False


def tasks() -> dict:
    from evaluation.tasks.condefects import ConDefectsTask
    from evaluation.tasks.quixbugs import QuixBugsTask

    found = {}
    if BENCHMARKS["condefects"]:
        found["condefects"] = ConDefectsTask(CODE / BENCHMARKS["condefects"])
    if BENCHMARKS["quixbugs"]:
        found["quixbugs"] = QuixBugsTask(CODE / BENCHMARKS["quixbugs"])
    return found


def evaluate(model_id: str) -> None:
    from evaluation.client import ChatClient
    from evaluation.run import RunConfig, run_benchmark, two_step

    server, served = MODELS[model_id]
    port = SERVERS[server][3]
    client = ChatClient(f"http://127.0.0.1:{port}/v1", model=served)

    def call(messages):
        return client.complete(messages, max_tokens=MAX_TOKENS, temperature=0.0, seed=3407)

    for name, task in tasks().items():
        config = RunConfig(benchmark=name, model_id=model_id, runtime="vllm", max_tokens=MAX_TOKENS,
                           base_url=f"http://127.0.0.1:{port}/v1", workers=16, dataset=task.dataset[0],
                           dataset_revision=task.dataset[1], generate_only=True,
                           notes="kaggle T4, vLLM 0.29; pre-registered repair check" + (" (format check)" if PILOT else ""))
        begin = time.time()
        summary = run_benchmark(config, task, task.load(), lambda item, t=task: two_step(t, item, call),
                                RESULTS / name / model_id)
        log(f"{model_id} {name}: {summary['metrics']['n']} answers in {time.time() - begin:.0f}s")


def stop(server: subprocess.Popen) -> None:
    server.terminate()
    try:
        server.wait(timeout=120)
    except subprocess.TimeoutExpired:
        server.kill()


def run_gpu(gpu: int, adapters: dict[str, Path]) -> None:
    """The servers of one GPU one after the other: two vLLM engines starting together on one T4
    both failed to find memory for their cache."""
    for name, (*_, server_gpu, port, _share) in SERVERS.items():
        if server_gpu != gpu:
            continue
        server = start(name, adapters)
        try:
            if not wait_healthy(port, server):
                raise RuntimeError(f"server {name} failed to start, see logs/vllm-{name}.log")
            log(f"server {name} ready")
            models = [m for m, (srv, _) in MODELS.items() if srv == name]
            with ThreadPoolExecutor(max_workers=len(models)) as pool:
                list(pool.map(evaluate, models))
        finally:
            stop(server)


def main() -> None:
    setup()
    adapters = adapter_paths()
    gpus = sorted({gpu for _, _, gpu, _, _ in SERVERS.values()})
    with ThreadPoolExecutor(max_workers=len(gpus)) as pool:
        list(pool.map(lambda g: run_gpu(g, adapters), gpus))
    (WORK / "done.json").write_text(json.dumps({"models": list(MODELS)}))
    log("all done")


if __name__ == "__main__":
    main()
