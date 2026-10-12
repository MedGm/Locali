"""Generate answers for chosen tasks with a base model and its LoRA adapter, side by side.

GPU 0 serves the base model, GPU 1 serves base + adapter (vLLM LoRA); both run the same tasks in
generate-only mode with identical prompts and decoding. Scoring happens locally in the sandbox.

Inputs (Kaggle datasets): the mixture (for internal_* tasks) and the adapter directory.
Environment variables:
    MODEL_ID=qwen2.5-coder-1.5b  ADAPTER_ID=qwen2.5-coder-1.5b-ft-qlora
    TASKS=internal_t1,internal_t2,internal_t3   LIMIT=  (items per task, smoke runs)
"""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = "https://github.com/MedGm/Locali.git"
COMMIT = "__LOCALI_COMMIT__"  # replaced when the notebook is built
CODE = Path("/tmp/locali")
WORK = Path("/kaggle/working")
MODELS = {
    "qwen2.5-coder-1.5b": ("Qwen/Qwen2.5-Coder-1.5B-Instruct", "2e1fd397ee46e1388853d2af2c993145b0f1098a"),
    "phi-4-mini": ("unsloth/Phi-4-mini-instruct", "75becc471c56fc34761ec998615ca6f8535c5a61"),
}


def main() -> None:
    logs = WORK / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    if not CODE.exists():
        subprocess.run(["git", "clone", REPO, str(CODE)], check=True)
    subprocess.run(["git", "-C", str(CODE), "checkout", COMMIT], check=True)
    sys.path.insert(0, str(CODE))
    with open(logs / "setup.log", "a") as fh:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "radon", "bandit", "datasets"],
                       stdout=fh, stderr=subprocess.STDOUT, check=True)
    from evaluation.gpu_energy import attach_gpu_energy
    from training.kaggle.common import (
        install_vllm,
        log,
        start_power_log,
        start_server,
        stop_server,
        wait_healthy,
    )

    model_id = os.environ.get("MODEL_ID", "qwen2.5-coder-1.5b")
    adapter_id = os.environ.get("ADAPTER_ID", f"{model_id}-ft-qlora")
    tasks = os.environ.get("TASKS", "internal_t1,internal_t2,internal_t3").split(",")
    limit = os.environ.get("LIMIT")
    repo, revision = MODELS[model_id]
    adapter_dir = min(Path("/kaggle/input").rglob("adapter_config.json")).parent
    mix_dir = next(p.parent for p in sorted(Path("/kaggle/input").rglob("test.jsonl")) if (p.parent / "train.jsonl").exists())
    log(f"adapter {adapter_dir}, mixture {mix_dir}")

    install_vllm(logs / "setup.log")
    power = start_power_log(WORK / "gpu_power.csv")
    lora = ["--enable-lora", "--max-lora-rank", "16", "--lora-modules", f"adapter={adapter_dir}"]
    queues = [(model_id, "local", [0], 8000, []), (adapter_id, "adapter", [1], 8001, lora)]

    def run_queue(run_id: str, served: str, gpus: list[int], port: int, extra: list[str]) -> None:
        server = start_server(repo, revision, gpus=gpus, port=port, logfile=logs / f"vllm_{run_id}.log", extra=extra)
        try:
            if not wait_healthy(port, server):
                log(f"{run_id}: server failed to start")
                return
            for task in tasks:
                out = WORK / "results" / task / f"{run_id}__fp16__kaggle-t4"
                cmd = [sys.executable, "-m", "evaluation.run", "--benchmark", task, "--generate-only",
                       "--workers", "16", "--model-id", run_id, "--model-revision", revision, "--quantization", "fp16",
                       "--runtime", "vLLM T4x1 eager" + (" + LoRA adapter" if extra else ""),
                       "--base-url", f"http://127.0.0.1:{port}/v1", "--served-model", served, "--out", str(out),
                       *(["--limit", limit] if limit else [])]
                start = time.time()
                with open(logs / f"run_{run_id}.log", "a") as fh:
                    rc = subprocess.run(cmd, cwd=CODE, stdout=fh, stderr=subprocess.STDOUT, check=False,
                                        env={**os.environ, "LOCALI_MIX_DIR": str(mix_dir)}).returncode
                if rc == 0 and (out / "summary.json").exists():
                    energy = attach_gpu_energy(out, (WORK / "gpu_power.csv").read_text(), gpus, start, time.time())
                    log(f"{run_id}/{task}: done, GPU energy {energy['total_j']} J")
                else:
                    log(f"{run_id}/{task}: FAILED rc={rc}")
        finally:
            stop_server(server)

    threads = [threading.Thread(target=run_queue, args=q) for q in queues]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    power.terminate()
    log("done")


if __name__ == "__main__":
    main()
