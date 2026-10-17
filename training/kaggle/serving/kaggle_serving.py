"""Serving efficiency of the merged model on Kaggle T4s (C4): KV cache, attention, batching.

GPU 0, vLLM (the serving stack of the T4 runs):
- prefix caching on vs off, at 1, 4 and 16 concurrent requests
- CUDA graphs vs --enforce-eager (every earlier T4 run used eager), at 1 and 16
- a warm pass: the same prompts again on the server that has just answered them (what a
  revalidation or a rerun of a patch costs)
Each run gets a fresh server, so one run's cache never helps the next. The workload is the first
64 held-out repair problems (internal_t1), generated here and scored locally in the sandbox, so
every configuration is also checked for changed answers.

GPU 1, transformers (the textbook knobs, on 16 of the same prompts):
- attention: SDPA vs eager, at batch 1 and batch 8
- KV cache on vs off (use_cache), batch 1, 4 prompts, 128 new tokens

Environment: PILOT=1 runs 4 items and a reduced grid, to check the flags before a full run.
"""

import json
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
POWER_LOG = WORK / "gpu_power.csv"
MODEL = "MedGm/Llama-Locali-Qwen2.5-Coder-1.5B"
REVISION = "a1b0b1189d2050dd20013371fc327362ea6b2964"
PILOT = os.environ.get("PILOT") == "1"
ITEMS = 4 if PILOT else 64

# (name, vLLM flags, concurrency levels)
SERVER_CONFIGS = [
    ("prefix-on-eager", ["--enable-prefix-caching", "--enforce-eager"], [1, 4] if PILOT else [1, 4, 16]),
    ("prefix-off-eager", ["--no-enable-prefix-caching", "--enforce-eager"], [1, 4] if PILOT else [1, 4, 16]),
    ("prefix-on-graphs", ["--enable-prefix-caching"], [1] if PILOT else [1, 16]),
]
WARM = ("prefix-on-eager", 4 if PILOT else 16)  # this run is followed by a second pass on the same server


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


def harness(name: str, workers: int, port: int) -> dict | None:
    out = RESULTS / "internal_t1" / name
    cmd = [
        sys.executable, "-m", "evaluation.run", "--benchmark", "internal_t1", "--generate-only",
        "--workers", str(workers), "--limit", str(ITEMS), "--model-id", "qwen2.5-coder-1.5b-ft-qlora-v2-merged",
        "--model-revision", REVISION, "--quantization", "fp16", "--runtime", f"vLLM {VLLM_VERSION} T4 {name}",
        "--base-url", f"http://127.0.0.1:{port}/v1", "--out", str(out),
        "--notes", f"C4 serving run {name}; scored locally in Docker sandbox",
    ]
    start = time.time()
    rc = sh(cmd, LOGS / f"run_{name}.log", cwd=CODE)
    end = time.time()
    if rc != 0 or not (out / "summary.json").exists():
        log(f"{name}: FAILED rc={rc}")
        return None
    sys.path.insert(0, str(CODE))
    from evaluation.gpu_energy import attach_gpu_energy

    energy = attach_gpu_energy(out, POWER_LOG.read_text(), [0], start, end)
    m = json.loads((out / "summary.json").read_text())["metrics"]
    row = {"run": name, "workers": workers, "items": m["n"], "wall_s": round(end - start, 2),
           "output_tokens": round(m["mean_output_tokens"] * m["n"]),
           "mean_ttft_s": m.get("mean_ttft_s"), "mean_total_s": m.get("mean_total_s"),
           "gpu_energy_j": energy["total_j"]}
    row["throughput_tok_s"] = round(row["output_tokens"] / row["wall_s"], 1)
    log(f"{name}: {m['n']} answers in {row['wall_s']:.0f}s, {row['throughput_tok_s']} tok/s, "
        f"TTFT {row['mean_ttft_s']}, {energy['total_j']} J")
    return row


def vllm_runs() -> None:
    rows = []
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": "0"}
    for config, flags, levels in SERVER_CONFIGS:
        for workers in levels:
            name = f"{config}__c{workers}"
            cmd = [str(VLLM_VENV / "bin" / "vllm"), "serve", MODEL, "--revision", REVISION,
                   "--served-model-name", "local", "--port", "8000", "--dtype", "half", "--max-model-len", "4096",
                   "--gpu-memory-utilization", "0.90", "--seed", "3407", *flags]
            with open(LOGS / f"vllm_{name}.log", "w") as fh:
                server = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env)
            try:
                if not wait_healthy(8000, server):
                    log(f"{name}: server failed to start")
                    continue
                row = harness(name, workers, 8000)
                if row:
                    rows.append(row | {"config": config})
                if (config, workers) == WARM:
                    warm = harness(f"{name}-warm", workers, 8000)
                    if warm:
                        rows.append(warm | {"config": config, "warm": True})
            finally:
                server.terminate()
                try:
                    server.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    server.kill()
            (WORK / "vllm_runs.json").write_text(json.dumps(rows, indent=1))
    log("vLLM runs done")


def hf_runs() -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = "1"
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer

    sys.path.insert(0, str(CODE))
    from evaluation.tasks.internal import InternalRepairTask

    task = InternalRepairTask()
    items = task.load(4 if PILOT else 16)
    tok = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
    tok.padding_side = "left"
    prompts = [tok.apply_chat_template(task.messages(i), tokenize=False, add_generation_prompt=True) for i in items]
    rows, texts = [], {}

    def bench(model, name: str, batch: int, n: int, new_tokens: int, use_cache: bool = True) -> None:
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        generated, outputs = 0, []
        start = time.time()
        for b in range(0, n, batch):
            enc = tok(prompts[b:b + batch], return_tensors="pt", padding=True).to("cuda")
            with torch.no_grad():
                out = model.generate(**enc, max_new_tokens=new_tokens, do_sample=False, use_cache=use_cache,
                                     pad_token_id=tok.pad_token_id)
            new = out[:, enc["input_ids"].shape[1]:]
            for seq in new:
                ids = [t for t in seq.tolist() if t != tok.pad_token_id]
                generated += len(ids)
                outputs.append(tok.decode(ids, skip_special_tokens=True))
        torch.cuda.synchronize()
        wall = time.time() - start
        rows.append({"run": name, "batch": batch, "prompts": n, "max_new_tokens": new_tokens, "use_cache": use_cache,
                     "wall_s": round(wall, 2), "generated_tokens": generated,
                     "tokens_per_s": round(generated / wall, 1),
                     "peak_memory_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2)})
        texts[name] = outputs
        log(f"hf {name}: {generated} tokens in {wall:.1f}s ({generated / wall:.1f} tok/s), "
            f"peak {rows[-1]['peak_memory_gb']} GB")

    n_all = len(prompts)
    for attn in ("sdpa", "eager"):
        model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION, torch_dtype=torch.float16,
                                                     attn_implementation=attn).to("cuda").eval()
        bench(model, f"{attn}__b1", 1, n_all, 256)
        bench(model, f"{attn}__b8", min(8, n_all), n_all, 256)
        if attn == "sdpa":
            n = min(4, n_all)
            bench(model, "sdpa__b1__cache-on__128", 1, n, 128, use_cache=True)
            bench(model, "sdpa__b1__cache-off__128", 1, n, 128, use_cache=False)
        del model
        torch.cuda.empty_cache()
    reference = texts["sdpa__b1"]
    for r in rows:
        same = [a == b for a, b in zip(texts[r["run"]], reference, strict=False)]
        r["same_answers_as_sdpa_b1"] = f"{sum(same)}/{len(same)}"
    out = {"transformers": transformers.__version__, "torch": torch.__version__, "gpu": torch.cuda.get_device_name(0),
           "rows": rows}
    (WORK / "hf_runs.json").write_text(json.dumps(out, indent=1))
    (WORK / "hf_answers.json").write_text(json.dumps(texts, indent=1))
    log("transformers runs done")


def main() -> None:
    setup()
    power = start_power_log()
    # transformers runs on GPU 1 in a child process, so CUDA_VISIBLE_DEVICES applies before torch loads
    hf = subprocess.Popen([sys.executable, __file__, "--hf"], env={**os.environ, "CUDA_VISIBLE_DEVICES": "1"},
                          stdout=open(LOGS / "hf.log", "w"), stderr=subprocess.STDOUT)  # noqa: SIM115
    vllm_runs()
    hf.wait()
    log(f"transformers process exit code {hf.returncode}")
    power.terminate()
    log("all done")


if __name__ == "__main__":
    if "--hf" in sys.argv:
        hf_runs()
    else:
        main()
