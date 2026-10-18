"""HumanEvalFix in JavaScript, Java, Go, C++ and Rust, base vs fine-tuned (Kaggle 2 x T4).

The fine-tune was trained on Python only. This measures whether repair in other languages got
better, stayed the same or got worse. Unlike every other experiment, the answers are compiled and
run here rather than in the laptop's sandbox (the toolchains for five languages do not fit its
disk); the VM is disposable, holds no secrets, and every program has a timeout.

1. install Node, a JDK, Go, g++ and Rust; check the harness on the reference solutions (all must
   pass) and the buggy ones (they should fail)
2. serve the merged fine-tune on GPU 0 and the base model on GPU 1 with vLLM, greedy, 768 tokens
3. generate one fix per problem and language, then compile and run each one

Environment: PILOT=1 runs 5 problems per language; LANGS=rust runs only the listed languages.
"""

import json
import os
import subprocess
import sys
import threading
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
LIMIT = 5 if os.environ.get("PILOT") == "1" else None
LANGS = os.environ.get("LANGS", "js,java,go,cpp,rust").split(",")
MODELS = {
    "ft": ("MedGm/Llama-Locali-Qwen2.5-Coder-1.5B", "a1b0b1189d2050dd20013371fc327362ea6b2964", 0, 8000),
    "base": ("Qwen/Qwen2.5-Coder-1.5B-Instruct", "2e1fd397ee46e1388853d2af2c993145b0f1098a", 1, 8001),
}


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
    assert sh(["apt-get", "update", "-qq"], setup_log) == 0
    assert sh(["apt-get", "install", "-y", "-qq", "nodejs", "npm", "default-jdk-headless", "golang-go", "g++", "cargo",
                                         "libboost-dev", "libssl-dev"],
              setup_log, env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"}) == 0, "toolchains failed"
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


def validate() -> dict:
    from evaluation.tasks.humanevalfix_multi import Runner, extract, load, program, reference_answer

    report = {}
    for lang in LANGS:
        items, runner = load(lang, LIMIT), Runner(lang)
        row = {}
        for which in ("canonical_solution", "buggy_solution"):
            outcomes = [runner.run(program(it, extract(reference_answer(it, getattr(it, which))))) for it in items]
            row[which] = {"passed": sum(o["passed"] for o in outcomes), "n": len(outcomes)}
            failures = [(it.task_id, o["status"], o["stderr"][:400]) for it, o in zip(items, outcomes, strict=True)
                        if which == "canonical_solution" and not o["passed"]]
            row["canonical_failures"] = row.get("canonical_failures", []) + failures
        runner.close()
        report[lang] = row
        log(f"validation {lang}: canonical {row['canonical_solution']}, buggy {row['buggy_solution']}")
    (WORK / "validation.json").write_text(json.dumps(report, indent=1))
    return report


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


def generate(key: str) -> None:
    from evaluation.client import ChatClient
    from evaluation.tasks.humanevalfix_multi import load, messages

    repo, revision, gpu, port = MODELS[key]
    cmd = [str(VLLM_VENV / "bin" / "vllm"), "serve", repo, "--revision", revision, "--served-model-name", "local",
           "--port", str(port), "--dtype", "half", "--max-model-len", "4096", "--gpu-memory-utilization", "0.90",
           "--seed", "3407"]
    with open(LOGS / f"vllm_{key}.log", "w") as fh:
        server = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                  env={**os.environ, "CUDA_VISIBLE_DEVICES": str(gpu)})
    try:
        if not wait_healthy(port, server):
            log(f"{key}: server failed to start")
            return
        client = ChatClient(f"http://127.0.0.1:{port}/v1")
        for lang in LANGS:
            items = load(lang, LIMIT)

            def ask(it):
                c = client.complete(messages(it), max_tokens=768)
                return {"task_id": it.task_id, "completion": c.text, "input_tokens": c.input_tokens,
                        "output_tokens": c.output_tokens, "total_s": c.total_s, "finish_reason": c.finish_reason}

            with ThreadPoolExecutor(16) as pool:
                rows = list(pool.map(ask, items))
            out = RESULTS / key / lang
            out.mkdir(parents=True, exist_ok=True)
            (out / "answers.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            log(f"{key}/{lang}: {len(rows)} answers")
    finally:
        server.terminate()
        try:
            server.wait(timeout=120)
        except subprocess.TimeoutExpired:
            server.kill()


def score() -> None:
    from evaluation.tasks.humanevalfix_multi import Runner, extract, load, program

    summary = {}
    for lang in LANGS:
        items = {it.task_id: it for it in load(lang, LIMIT)}
        runner = Runner(lang)
        for key in MODELS:
            path = RESULTS / key / lang / "answers.jsonl"
            if not path.exists():
                continue
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            for r in rows:
                it = items[r["task_id"]]
                outcome = runner.run(program(it, extract(r["completion"])))
                r.update(passed=outcome["passed"], status=outcome["status"], stderr=outcome["stderr"][:600],
                         bug_type=it.bug_type)
            (RESULTS / key / lang / "samples.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            passed = sum(r["passed"] for r in rows)
            summary.setdefault(lang, {})[key] = {"passed": passed, "n": len(rows),
                                                 "pass@1": round(passed / len(rows) * 100, 1) if rows else None}
            log(f"score {key}/{lang}: {passed}/{len(rows)}")
        runner.close()
    (WORK / "summary.json").write_text(json.dumps(summary, indent=1))


def main() -> None:
    setup()
    report = validate()
    if any(r["canonical_solution"]["passed"] < r["canonical_solution"]["n"] for r in report.values()):
        log("some reference solutions fail; see validation.json (scores are still computed)")
    threads = [threading.Thread(target=generate, args=(key,)) for key in MODELS]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    score()
    log("all done")


if __name__ == "__main__":
    main()
