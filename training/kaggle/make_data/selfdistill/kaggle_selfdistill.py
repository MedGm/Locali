"""Base Qwen2.5-Coder-3B answers to the replay prompts of mixture v3b (2 x T4, vLLM, TP=2).

Input: Kaggle dataset `locali-mix-v3b` (train/val/test.jsonl; rows with task "replay").
Output: /kaggle/working/answers.jsonl, one line per prompt: {id, text, finish_reason,
output_tokens, status}. status is "passed" when the answer finished, its Python parses and runs
without error in evaluation/isolated.py (10 s), else why not. The mixture is rebuilt locally
(training/data/build_mix_v3s.py). Greedy, same chat template as training. PILOT=1: 32 prompts.
"""

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = "https://github.com/MedGm/Locali.git"
COMMIT = "__LOCALI_COMMIT__"  # replaced when the notebook is built
CODE = Path("/tmp/locali")
WORK = Path("/kaggle/working")
INPUT_ROOT = Path("/kaggle/input")
BASE = ("Qwen/Qwen2.5-Coder-3B-Instruct", "488639f1ff808d1d3d0ba301aef8c11461451ec5")
PORT = 8000
MAX_TOKENS = 1024
LIMIT = 32 if os.environ.get("PILOT") == "1" else None


def main() -> None:
    logs = WORK / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    if not CODE.exists():
        subprocess.run(["git", "clone", REPO, str(CODE)], check=True)
    subprocess.run(["git", "-C", str(CODE), "checkout", COMMIT], check=True)
    sys.path.insert(0, str(CODE))
    from evaluation import isolated
    from training.data.selfdistill import replay_prompts, runnable_code
    from training.kaggle.common import (
        install_vllm,
        log,
        run_requests,
        start_server,
        stop_server,
        wait_healthy,
    )

    rows = []
    for split in ("train", "val", "test"):
        path = min(INPUT_ROOT.rglob(f"{split}.jsonl"))
        rows += [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    jobs = replay_prompts(rows)[:LIMIT]
    log(f"{len(jobs)} replay prompts; network isolation {isolated.network_isolation()}")

    install_vllm(logs / "setup.log")
    raw = WORK / "raw.jsonl"
    server = start_server(*BASE, gpus=[0, 1], port=PORT, logfile=logs / "vllm.log")
    try:
        if not wait_healthy(PORT, server):
            raise RuntimeError("server failed to start, see logs/vllm.log")
        log("server ready")
        start = time.time()
        run_requests(PORT, jobs, raw, max_tokens=MAX_TOKENS, workers=64)
        log(f"generated in {time.time() - start:.0f}s")
    finally:
        stop_server(server)

    answers = [json.loads(line) for line in raw.read_text().splitlines() if line.strip()]

    def check(answer: dict) -> dict:
        code = runnable_code(answer)
        if code is None:
            status = "error" if "error" in answer else "length" if answer.get("finish_reason") == "length" else "no_code"
        else:
            status = isolated.run_isolated(code, timeout_s=10, memory_mb=1024).status
        return answer | {"status": status}

    with ThreadPoolExecutor(max_workers=8) as pool:
        checked = list(pool.map(check, answers))
    with (WORK / "answers.jsonl").open("w") as fh:
        for a in checked:
            fh.write(json.dumps(a) + "\n")
    counts = {}
    for a in checked:
        counts[a["status"]] = counts.get(a["status"], 0) + 1
    log(f"status counts: {counts}")
    log("all done")


if __name__ == "__main__":
    main()
