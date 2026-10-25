"""Rewrite the v3 bug notes as reviewer diagnoses (Qwen3.5-9B on 2 x T4, TP=2).

The teacher's note on each realistic bug says what it changed ("Changed x to y"), from the side of
whoever made the bug. The repair examples need what a reviewer would say about the buggy code.
For each bug the teacher sees the buggy and the correct code and its own note
(training/data/v3_repair.py: diagnosis_messages); the answer is kept only if accept_diagnosis passes
(complete, short, not phrased as an edit, names something in the changed lines). A rejected answer
is asked again once at temperature 0.6. Output: diagnoses.jsonl (source, diagnosis or null).

Input: Kaggle dataset locali-v3-diagnosis-inputs (diag_inputs.jsonl).
"""

import json
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = "https://github.com/MedGm/Locali.git"
COMMIT = "__LOCALI_COMMIT__"  # replaced when the notebook is built
CODE = Path("/tmp/locali")
WORK = Path("/kaggle/working")
TEACHER = ("Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a")
PORT = 8000


def ask(messages: list[dict], temperature: float) -> str:
    body = {"model": "local", "messages": messages, "max_tokens": 200, "temperature": temperature, "seed": 3407,
            "chat_template_kwargs": {"enable_thinking": False}}
    request = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.load(response)["choices"][0]["message"]["content"]


def main() -> None:
    (WORK / "logs").mkdir(parents=True, exist_ok=True)
    if not CODE.exists():
        subprocess.run(["git", "clone", "-q", REPO, str(CODE)], check=True)
    subprocess.run(["git", "-C", str(CODE), "checkout", "-q", COMMIT], check=True)
    sys.path.insert(0, str(CODE))
    from training.data.v3_repair import accept_diagnosis, diagnosis_messages
    from training.kaggle.common import TEXT_ONLY, install_vllm, log, start_server, stop_server, wait_healthy

    found = next(Path("/kaggle/input").rglob("diag_inputs.jsonl"))
    rows = [json.loads(line) for line in found.read_text().splitlines() if line.strip()]
    log(f"{len(rows)} bugs")
    install_vllm(WORK / "logs" / "setup.log")
    server = start_server(*TEACHER, gpus=[0, 1], port=PORT, logfile=WORK / "logs" / "vllm.log", extra=TEXT_ONLY)
    try:
        if not wait_healthy(PORT, server):
            raise RuntimeError("teacher failed to start, see logs/vllm.log")
        log("teacher ready")

        def one(row):
            messages = diagnosis_messages(row["buggy"], row["fixed"], row["note"], row["kind"])
            replies = []
            for temperature in (0.0, 0.6):
                try:
                    text = ask(messages, temperature)
                except Exception as e:
                    replies.append(f"request failed: {type(e).__name__}")
                    continue
                replies.append(text)
                accepted = accept_diagnosis(text, row["bug_line"], row["changed"])
                if accepted:
                    return {"source": row["source"], "diagnosis": accepted, "attempt": len(replies)}
            return {"source": row["source"], "diagnosis": None, "replies": replies}

        start = time.time()
        with ThreadPoolExecutor(32) as pool:
            out = list(pool.map(one, rows))
        log(f"done in {time.time() - start:.0f}s")
    finally:
        stop_server(server)
    (WORK / "diagnoses.jsonl").write_text("".join(json.dumps(r) + "\n" for r in out))
    kept = sum(r["diagnosis"] is not None for r in out)
    log(f"accepted {kept} of {len(out)} ({kept / len(out):.0%}); first attempt "
        f"{sum(r.get('attempt') == 1 for r in out)}")


if __name__ == "__main__":
    main()
