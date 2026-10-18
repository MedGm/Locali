"""Speculative decoding on Kaggle T4s: a 0.5B draft model or n-gram lookup, against plain decoding.

The laptop study (experiments/scripts/laptop_speculative.sh) measures the same on the CPU. Here:

- target: the merged fine-tune on GPU 0 and the base model on GPU 1, in parallel, so the draft's
  acceptance can be compared on a model it was not tuned with (the draft is the base 0.5B)
- settings: none, draft model with 2/4/8 drafted tokens, n-gram lookup with 4
- each setting at 1 concurrent request (latency) and 8 (where speculation usually pays less)
- benchmarks: HumanEval+ and HumanEvalFix (Python), 164 problems each, greedy, 768 tokens

Every run gets a fresh server. Answers are scored here with evaluation/isolated.py (no network,
own folder, limits, timeout) through the normal task scoring, energy comes from nvidia-smi, and
the draft counts from vLLM's Prometheus counters before and after each run.

Environment: PILOT=1 runs 8 problems, c1 only, and settings none/draft-n4/ngram-n4.
"""

import json
import os
import re
import subprocess
import sys
import threading
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
POWER_LOG = WORK / "gpu_power.csv"
PILOT = os.environ.get("PILOT") == "1"
LIMIT = 8 if PILOT else None
BENCHMARKS = ["humaneval_plus", "humanevalfix"]
CONCURRENCY = [1] if PILOT else [1, 8]
DRAFT = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
TARGETS = {  # key: (repo, revision, gpu, port)
    "ft": ("MedGm/Llama-Locali-Qwen2.5-Coder-1.5B", "a1b0b1189d2050dd20013371fc327362ea6b2964", 0, 8000),
    "base": ("Qwen/Qwen2.5-Coder-1.5B-Instruct", "2e1fd397ee46e1388853d2af2c993145b0f1098a", 1, 8001),
}
MODEL_IDS = {"ft": "qwen2.5-coder-1.5b-ft-qlora-v2-merged", "base": "qwen2.5-coder-1.5b-instruct"}


def settings(draft_revision: str) -> dict[str, dict | None]:
    draft = lambda n: {"method": "draft_model", "model": DRAFT, "revision": draft_revision,
                       "num_speculative_tokens": n}
    all_settings = {
        "none": None,
        "draft-n2": draft(2),
        "draft-n4": draft(4),
        "draft-n8": draft(8),
        "ngram-n4": {"method": "ngram", "num_speculative_tokens": 4, "prompt_lookup_min": 2, "prompt_lookup_max": 4},
    }
    keep = ("none", "draft-n4", "ngram-n4") if PILOT else all_settings
    return {k: all_settings[k] for k in keep}


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


def score_in_isolation() -> str:
    """Point the task scoring at the isolated runner instead of the laptop's Docker sandbox."""
    from evaluation import isolated
    from evaluation.tasks import codegen, humanevalpack

    def run_program(program: str, timeout_s: float = 60) -> codegen.Outcome:
        r = isolated.run_isolated(program, timeout_s=min(timeout_s, 60))
        return codegen.Outcome(r.passed, r.status, r.error or "", r.seconds)

    codegen.run_program = run_program
    humanevalpack.run_program = run_program
    return isolated.network_isolation()


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


def spec_counters(port: int) -> dict[str, float]:
    """vLLM's speculative decoding counters (summed over labels), {} when it has none."""
    try:
        text = urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=10).read().decode()
    except OSError:
        return {}
    totals: dict[str, float] = {}
    for line in text.splitlines():
        m = re.match(r"vllm:spec_decode_(num_\w+?)(?:_total)?(?:\{[^}]*\})? ([0-9.eE+-]+)$", line)
        if m:
            totals[m.group(1)] = totals.get(m.group(1), 0.0) + float(m.group(2))
    return totals


def one_run(key: str, setting: str, bench: str, workers: int, port: int) -> dict | None:
    from evaluation.gpu_energy import attach_gpu_energy
    from evaluation.rescore import rescore_run
    from evaluation.run import TASKS

    _, revision, gpu, _ = TARGETS[key]
    name = f"{setting}__c{workers}"
    out = RESULTS / key / bench / name
    cmd = [sys.executable, "-m", "evaluation.run", "--benchmark", bench, "--generate-only",
           "--workers", str(workers), "--model-id", MODEL_IDS[key], "--model-revision", revision,
           "--quantization", "fp16", "--runtime", f"vLLM {VLLM_VERSION} T4, speculative: {setting}",
           "--base-url", f"http://127.0.0.1:{port}/v1", "--out", str(out),
           "--notes", f"speculative decoding study on a T4 ({setting}, {workers} concurrent)",
           *(["--limit", str(LIMIT)] if LIMIT else [])]
    before = spec_counters(port)
    start = time.time()
    rc = sh(cmd, LOGS / f"run_{key}_{bench}_{name}.log", cwd=CODE)
    end = time.time()
    after = spec_counters(port)
    if rc != 0 or not (out / "summary.json").exists():
        log(f"{key}/{bench}/{name}: FAILED rc={rc}")
        return None
    energy = attach_gpu_energy(out, POWER_LOG.read_text(), [gpu], start, end)
    task = TASKS[bench]
    summary = rescore_run(out, task, task.load(LIMIT), workers=8)
    draft = {k: after[k] - before.get(k, 0.0) for k in after}
    summary["speculative"] = {"setting": setting, "vllm_counters": draft}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    m = summary["metrics"]
    passed = round(m["pass@1"] * m["n"]) if "pass@1" in m else None
    row = {"target": key, "benchmark": bench, "setting": setting, "workers": workers, "n": m["n"],
           "passed": passed, "wall_s": round(end - start, 1),
           "output_tokens": round(m["mean_output_tokens"] * m["n"]), "gpu_energy_j": energy["total_j"],
           "draft_tokens": draft.get("num_draft_tokens"), "accepted_tokens": draft.get("num_accepted_tokens")}
    row["tokens_per_s"] = round(row["output_tokens"] / row["wall_s"], 1)
    if row["draft_tokens"]:
        row["acceptance"] = round(row["accepted_tokens"] / row["draft_tokens"], 3)
    if passed and energy["total_j"]:
        row["j_per_correct"] = round(energy["total_j"] / passed, 1)
    log(f"{key}/{bench}/{name}: {passed}/{m['n']} passed, {row['tokens_per_s']} tok/s, "
        f"{energy['total_j']} J, acceptance {row.get('acceptance')}")
    return row


def run_target(key: str, configs: dict[str, dict | None], rows: list, lock: threading.Lock) -> None:
    repo, revision, gpu, port = TARGETS[key]
    for setting, spec in configs.items():
        cmd = [str(VLLM_VENV / "bin" / "vllm"), "serve", repo, "--revision", revision, "--served-model-name", "local",
               "--port", str(port), "--dtype", "half", "--max-model-len", "4096", "--gpu-memory-utilization", "0.90",
               "--seed", "3407", *(["--speculative-config", json.dumps(spec)] if spec else [])]
        with open(LOGS / f"vllm_{key}_{setting}.log", "w") as fh:
            server = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                      env={**os.environ, "CUDA_VISIBLE_DEVICES": str(gpu)})
        try:
            if not wait_healthy(port, server):
                log(f"{key}/{setting}: server failed to start, see logs/vllm_{key}_{setting}.log")
                continue
            for bench in BENCHMARKS:
                for workers in CONCURRENCY:
                    row = one_run(key, setting, bench, workers, port)
                    if row:
                        with lock:
                            rows.append(row)
                            (WORK / "runs.json").write_text(json.dumps(rows, indent=1))
        finally:
            server.terminate()
            try:
                server.wait(timeout=120)
            except subprocess.TimeoutExpired:
                server.kill()


def same_answers() -> dict:
    """How many answers of each setting are identical to plain decoding's (greedy, same target)."""
    report = {}
    for target_dir in sorted(RESULTS.iterdir()):
        for bench_dir in sorted(target_dir.iterdir()):
            def answers(run: Path) -> dict:
                lines = (run / "samples.jsonl").read_text().splitlines()
                return {r["task_id"]: r["completion"] for r in map(json.loads, lines)}
            for workers in CONCURRENCY:
                ref_dir = bench_dir / f"none__c{workers}"
                if not ref_dir.exists():
                    continue
                ref = answers(ref_dir)
                for run in sorted(bench_dir.glob(f"*__c{workers}")):
                    got = answers(run)
                    same = sum(got.get(t) == a for t, a in ref.items())
                    report[f"{target_dir.name}/{bench_dir.name}/{run.name}"] = f"{same}/{len(ref)}"
    return report


def main() -> None:
    setup()
    from huggingface_hub import HfApi

    draft_revision = HfApi().model_info(DRAFT).sha
    isolation = score_in_isolation()
    log(f"draft {DRAFT}@{draft_revision}, network isolation: {isolation}")
    configs = settings(draft_revision)
    (WORK / "config.json").write_text(json.dumps({"draft": DRAFT, "draft_revision": draft_revision,
                                                  "network_isolation": isolation, "settings": configs,
                                                  "concurrency": CONCURRENCY, "limit": LIMIT}, indent=1))
    power = start_power_log()
    rows, lock = [], threading.Lock()
    threads = [threading.Thread(target=run_target, args=(k, configs, rows, lock)) for k in TARGETS]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    power.terminate()
    (WORK / "same_answers.json").write_text(json.dumps(same_answers(), indent=1))
    log("all done")


if __name__ == "__main__":
    main()
