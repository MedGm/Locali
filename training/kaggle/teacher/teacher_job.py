"""Teacher explanations for T1 bug examples with Qwen3.5-9B on Kaggle (2 x T4, vLLM, TP=2).

Input: Kaggle dataset `locali-teacher-inputs` with t1.jsonl (cleaned T1 examples).
Output: /kaggle/working/explanations.jsonl ({id, text, finish_reason, output_tokens}); the
acceptance check and template fallback run locally (training.data.teacher.accept_explanation).
"""

import json
import subprocess
import sys
import time
from pathlib import Path

REPO = "https://github.com/MedGm/Locali.git"
COMMIT = "__LOCALI_COMMIT__"  # replaced when the notebook is built
CODE = Path("/tmp/locali")
WORK = Path("/kaggle/working")
INPUT_ROOT = Path("/kaggle/input")  # dataset mount layout varies; the file is located by name
TEACHER = ("Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a")
PORT = 8000


def main() -> None:
    logs = WORK / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    if not CODE.exists():
        subprocess.run(["git", "clone", REPO, str(CODE)], check=True)
    subprocess.run(["git", "-C", str(CODE), "checkout", COMMIT], check=True)
    sys.path.insert(0, str(CODE))
    from training.data.teacher import teacher_messages
    from training.kaggle.common import (
        TEXT_ONLY,
        install_vllm,
        log,
        run_requests,
        start_power_log,
        start_server,
        stop_server,
        wait_healthy,
    )

    found = sorted(INPUT_ROOT.rglob("t1.jsonl"))
    if not found:
        listing = "\n".join(str(p) for p in INPUT_ROOT.rglob("*"))
        raise FileNotFoundError(f"t1.jsonl not found under {INPUT_ROOT}:\n{listing}")
    log(f"input: {found[0]}")
    examples = [json.loads(line) for line in found[0].read_text().splitlines() if line.strip()]
    log(f"{len(examples)} examples")
    install_vllm(logs / "setup.log")
    power = start_power_log(WORK / "gpu_power.csv")
    server = start_server(*TEACHER, gpus=[0, 1], port=PORT, logfile=logs / "vllm.log", extra=TEXT_ONLY)
    try:
        if not wait_healthy(PORT, server):
            raise RuntimeError("teacher server failed to start, see logs/vllm.log")
        log("teacher ready")
        start = time.time()
        jobs = [(ex["id"], teacher_messages(ex)) for ex in examples]
        run_requests(PORT, jobs, WORK / "explanations.jsonl", max_tokens=160, workers=32)
        log(f"done in {time.time() - start:.0f}s")
    finally:
        stop_server(server)
        power.terminate()


if __name__ == "__main__":
    main()
