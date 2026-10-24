"""v3 data: realistic bugs from the teacher (Qwen3.5-9B, 2 x T4, TP=2), verified by the unit tests.

1. sample CodeRM-UnitTest problems not used by mixtures v1/v2 (training/data/coderm_used_ids.txt),
   short functions with a reliable test suite, as for T1
2. run each problem's tests on its reference solution in evaluation/isolated.py; keep those that pass
3. ask the teacher for one bug of a given kind (training/data/realistic_bugs.py), logic bugs
   weighted up, temperature 0.6, up to 3 attempts per problem
4. keep a bug only if it passes the static checks and the tests fail on it

Output: bugs.jsonl (kept, with the failing test's error), rejected.jsonl (with the reason), stats.json.

Environment: N=300 problems (pilot); SAMPLE_SEED=41.
"""

import json
import os
import random
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = "https://github.com/MedGm/Locali.git"
COMMIT = "__LOCALI_COMMIT__"  # replaced when the notebook is built
CODE = Path("/tmp/locali")
WORK = Path("/kaggle/working")
TEACHER = ("Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a")
PORT = 8000
N = int(os.environ.get("N", "300"))
SAMPLE_SEED = int(os.environ.get("SAMPLE_SEED", "41"))
TEMPERATURE = 0.6
ATTEMPTS = 3  # a rejected bug is asked for again, with another sampling seed
KIND_WEIGHTS = {"missing_logic": 3, "excess_logic": 2}


def setup() -> None:
    (WORK / "logs").mkdir(parents=True, exist_ok=True)
    if not CODE.exists():
        subprocess.run(["git", "clone", REPO, str(CODE)], check=True)
    subprocess.run(["git", "-C", str(CODE), "checkout", COMMIT], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "datasets"], check=True)
    sys.path.insert(0, str(CODE))


def teacher_bug(port: int, messages: list[dict], seed: int) -> dict:
    import urllib.request

    body = {"model": "local", "messages": messages, "max_tokens": 1024, "temperature": TEMPERATURE,
            "seed": seed, "chat_template_kwargs": {"enable_thinking": False}}
    request = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.load(response)


def main() -> None:
    setup()
    from datasets import load_dataset

    from evaluation.isolated import network_isolation, run_isolated
    from training.data.realistic_bugs import (
        BUG_KINDS,
        bug_messages,
        check_candidate,
        parse_reply,
        strip_comments,
        unittest_program,
    )
    from training.data.t1_bugs import SOURCE, SOURCE_REVISION, select_seeds
    from training.kaggle.common import (
        TEXT_ONLY,
        install_vllm,
        log,
        start_power_log,
        start_server,
        stop_server,
        wait_healthy,
    )

    used = set((CODE / "training" / "data" / "coderm_used_ids.txt").read_text().split())
    rows = load_dataset(SOURCE, revision=SOURCE_REVISION, split="train")
    fresh = [s for s in select_seeds(rows, n=len(rows), seed=SAMPLE_SEED) if s.task_id not in used]
    log(f"{len(fresh)} unused problems with a reliable suite; network isolation: {network_isolation()}")

    # reference solutions must pass their own tests; sample until N do
    candidates = fresh[: N * 2]
    with ThreadPoolExecutor(8) as pool:
        ok = list(pool.map(lambda s: run_isolated(unittest_program(s.code, s.tests), timeout_s=30).passed, candidates))
    seeds = [s for s, good in zip(candidates, ok, strict=True) if good][:N]
    log(f"{sum(ok)} of {len(candidates)} reference solutions pass; using {len(seeds)}")

    # logic bugs are where the v2 model is weakest (docs/retrospective.md), so they get a larger share
    kinds = [k for k in BUG_KINDS for _ in range(KIND_WEIGHTS.get(k, 1))]
    random.Random(SAMPLE_SEED).shuffle(kinds)
    jobs = [(s, kinds[i % len(kinds)]) for i, s in enumerate(seeds)]

    install_vllm(WORK / "logs" / "setup.log")
    power = start_power_log(WORK / "gpu_power.csv")
    server = start_server(*TEACHER, gpus=[0, 1], port=PORT, logfile=WORK / "logs" / "vllm.log", extra=TEXT_ONLY)
    kept, rejected = [], []
    try:
        if not wait_healthy(PORT, server):
            raise RuntimeError("teacher server failed to start, see logs/vllm.log")
        log("teacher ready")
        start = time.time()

        def attempt(seed_obj, kind, n):
            try:
                reply = teacher_bug(PORT, bug_messages(seed_obj.question, seed_obj.code, kind), SAMPLE_SEED + n)
                text = reply["choices"][0]["message"]["content"]
            except Exception as e:
                return None, f"request failed: {type(e).__name__}", ""
            description, candidate = parse_reply(text)
            accepted, reason = check_candidate(seed_obj.code, candidate, kind=kind)
            if not accepted:
                return None, reason, text
            buggy = strip_comments(candidate)
            result = run_isolated(unittest_program(buggy, seed_obj.tests), timeout_s=30)
            if result.passed:
                return None, "tests still pass", text
            if result.status == "timeout":
                return None, "timeout", text
            return {"buggy_code": buggy, "description": description, "error": result.error}, "ok", text

        def one(job):
            seed_obj, kind = job
            base = {"source": f"{SOURCE}:{seed_obj.task_id}", "kind": kind}
            reasons = []
            for n in range(ATTEMPTS):
                bug, reason, text = attempt(seed_obj, kind, n)
                if bug:
                    return True, base | bug | {"attempt": n + 1, "question": seed_obj.question,
                                               "fixed_code": strip_comments(seed_obj.code),
                                               "original_code": seed_obj.code, "tests": seed_obj.tests}
                reasons.append(reason)
            return False, base | {"reason": reasons[-1], "reasons": reasons, "reply": text[:2000]}

        # results are appended as they come, so a run stopped by Kaggle's time limit keeps what it made
        with ThreadPoolExecutor(32) as pool, (WORK / "bugs.jsonl").open("w") as good, \
                (WORK / "rejected.jsonl").open("w") as bad:
            for i, (accepted, row) in enumerate(pool.map(one, jobs), 1):
                (kept if accepted else rejected).append(row)
                (good if accepted else bad).write(json.dumps(row) + "\n")
                if i % 250 == 0:
                    good.flush()
                    bad.flush()
                    log(f"{i} of {len(jobs)} problems done, {len(kept)} bugs kept")
        log(f"teacher and checks done in {time.time() - start:.0f}s")
    finally:
        stop_server(server)
        power.terminate()

    stats = {"problems": len(seeds), "kept": len(kept), "kept_by_kind": dict(Counter(r["kind"] for r in kept)),
             "rejected_by_reason": dict(Counter(r["reason"] for r in rejected)),
             "kept_by_attempt": dict(Counter(r["attempt"] for r in kept)),
             "teacher": TEACHER, "temperature": TEMPERATURE, "attempts": ATTEMPTS, "kind_weights": KIND_WEIGHTS, "sample_seed": SAMPLE_SEED, "commit": COMMIT}
    (WORK / "stats.json").write_text(json.dumps(stats, indent=1))
    log(json.dumps(stats))


if __name__ == "__main__":
    main()
