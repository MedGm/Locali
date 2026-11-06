"""Capability study, step 3 (T4): how many decisions separate a fine-tuned model's wrong answer
from the base's right one, and the other way round?

Forced-divergence walk. For every HumanEval+ problem where one model's greedy answer (step 2,
experiments/results/3_finetune_3b/capability_study/step2_kaggle) passes and another's fails, the failing model
(the follower) answers greedily from the prompt. At the first token where its answer leaves the
passing model's answer (the leader), the leader's token is forced, and the follower continues
greedily from there. This repeats until the follower's answer passes, follows the leader to the
end, or MAX_FORCED tokens have been forced. Each step records the follower's top 5 alternatives
at the divergence and the rank of the leader's token (evaluation/divergence.py).

Models: base Qwen2.5-Coder-3B ("local"), run D and run E adapters, one vLLM server. Model-written
code runs in evaluation/isolated.py. PILOT=1: 4 walks.
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
COMMIT = "__LOCALI_COMMIT__"  # replaced when the notebook is built
WORK = Path("/kaggle/working")
CODE = Path("/tmp/locali")
VLLM_VENV = Path("/tmp/venv-vllm")
VLLM_VERSION = "0.29.0"
LOGS = WORK / "logs"
BASE = ("Qwen/Qwen2.5-Coder-3B-Instruct", "488639f1ff808d1d3d0ba301aef8c11461451ec5")
ADAPTERS = ("mixv3b-diag", "mixv3s")
MODELS = {"qwen2.5-coder-3b": "local", "qwen2.5-coder-3b-ft-qlora-mixv3b-diag": "mixv3b-diag",
          "qwen2.5-coder-3b-ft-qlora-mixv3s": "mixv3s"}  # model id: served name
STEP2 = CODE / "experiments" / "results" / "3_finetune_3b/capability_study" / "step2_kaggle" / "results" / "humaneval_plus"
MAX_FORCED = 12
N_CONTROL = 5  # control nudges per walk, of each kind
PILOT = os.environ.get("PILOT") == "1"
PORT = 8000
URL = f"http://127.0.0.1:{PORT}"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sh(cmd: list[str], logfile: Path, **kwargs) -> int:
    with open(logfile, "a") as fh:
        return subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, check=False, **kwargs).returncode


def post(path: str, body: dict, timeout: float = 600) -> dict:
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


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
    import evaluation.divergence  # noqa: F401 - fail here, not after the server has started
    log("setup done")


def score_in_isolation() -> str:
    from evaluation import isolated
    from evaluation.tasks import codegen

    def run_program(program: str, timeout_s: float = 60) -> codegen.Outcome:
        r = isolated.run_isolated(program, timeout_s=min(timeout_s, 60))
        return codegen.Outcome(r.passed, r.status, r.error or "", r.seconds)

    codegen.run_program = run_program
    return isolated.network_isolation()


def adapter_paths() -> dict[str, Path]:
    found = {p.parent.name: p.parent for p in Path("/kaggle/input").rglob("adapter_config.json")}
    missing = set(ADAPTERS) - set(found)
    assert not missing, f"adapters not found: {missing}; have {sorted(found)}"
    return {name: found[name] for name in ADAPTERS}


def wait_healthy(server: subprocess.Popen, timeout_s: float = 1800) -> bool:
    start = time.time()
    while time.time() - start < timeout_s:
        if server.poll() is not None:
            return False
        try:
            urllib.request.urlopen(f"{URL}/health", timeout=5)
            return True
        except OSError:
            time.sleep(5)
    return False


def ids(tokens: list[str]) -> list[int]:
    return [int(t.split(":", 1)[1]) for t in tokens]


def detok(served: str, tokens: list[int]) -> str:
    return post("/detokenize", {"model": served, "tokens": tokens})["prompt"] if tokens else ""


def walks() -> None:
    from evaluation.client import Completion
    from evaluation.divergence import (
        first_divergence,
        nudge_positions,
        rank_of,
        refence,
        second_choice,
        uncertain_positions,
    )
    from evaluation.run import TASKS

    task = TASKS["humaneval_plus"]
    items = {i.task_id: i for i in task.load(None)}
    greedy = {}
    for model_id in MODELS:
        path = STEP2 / f"{model_id}__fp16__kaggle-t4" / "samples.jsonl"
        greedy[model_id] = {r["task_id"]: r for r in map(json.loads, path.read_text().splitlines())}
    jobs = [(f, lead, t) for f in MODELS for lead in MODELS if f != lead
            for t in items if greedy[lead][t]["passed"] and not greedy[f][t]["passed"]]
    if PILOT:
        jobs = jobs[:4]
    log(f"walks: {len(jobs)}")

    def walk(job):
        follower, leader, task_id = job
        served, item = MODELS[follower], items[task_id]
        prompt = post("/tokenize", {"model": served, "messages": task.messages(item),
                                    "add_generation_prompt": True})["tokens"]
        own = greedy[follower][task_id]["completion"]
        lead = post("/tokenize", {"model": served, "prompt": refence(greedy[leader][task_id]["completion"], own),
                                  "add_special_tokens": False})["tokens"]
        steps, forced = [], 0
        for n in range(MAX_FORCED + 1):
            d = post("/v1/completions", {"model": served, "prompt": prompt + lead[:forced], "max_tokens": 768,
                                         "temperature": 0.0, "logprobs": 5, "return_tokens_as_token_ids": True})
            choice = d["choices"][0]
            cont = ids(choice["logprobs"]["tokens"])
            text = detok(served, lead[:forced]) + choice["text"]
            s = task.score(item, Completion(text, "", None, None, 0, 0, choice["finish_reason"]), 20)
            step = {"forced": n, "prefix_tokens": forced, "passed": s["passed"], "status": s["status"], "text": text}
            if n == 0:
                step["same_as_step2_greedy"] = text == own
            j = None if s["passed"] else first_divergence(cont, lead, forced)
            if j is not None:
                k = j - forced
                top = choice["logprobs"]["top_logprobs"][k]
                step["divergence"] = {
                    "position": j, "follower_token": cont[k], "leader_token": lead[j],
                    "follower_piece": detok(served, [cont[k]]), "leader_piece": detok(served, [lead[j]]),
                    "follower_logprob": choice["logprobs"]["token_logprobs"][k],
                    "leader_logprob": top.get(f"token_id:{lead[j]}"), "leader_rank": rank_of(lead[j], top),
                    "top": top, "line_before": detok(served, lead[:j]).rsplit("\n", 1)[-1],
                    "leader_rest_of_line": detok(served, lead[j:j + 40]).split("\n", 1)[0],
                    "follower_rest_of_line": detok(served, cont[k:k + 40]).split("\n", 1)[0]}
            steps.append(step)
            if j is None:
                break
            forced = j + 1
        return {"follower": follower, "leader": leader, "task_id": task_id, "leader_tokens": len(lead),
                "passed": steps[-1]["passed"], "steps": steps,
                "controls": controls(follower, leader, item, prompt, steps[0])}

    def controls(follower, leader, item, prompt, first):
        """Force the follower's own second choice instead of the leader's token, at random positions
        and at the positions where it was least sure, in its own greedy answer."""
        served = MODELS[follower]
        d = post("/v1/completions", {"model": served, "prompt": prompt, "max_tokens": 768, "temperature": 0.0,
                                     "logprobs": 5, "return_tokens_as_token_ids": True})["choices"][0]["logprobs"]
        own, chosen, tops = ids(d["tokens"]), d["token_logprobs"], d["top_logprobs"]
        j0 = first.get("divergence", {}).get("position")
        picks = [("random", p) for p in nudge_positions(len(own), N_CONTROL, seed=f"{follower}|{leader}|{item.task_id}")]
        picks += [("uncertain", p) for p in uncertain_positions(chosen, N_CONTROL, exclude=j0)]
        out = []
        for kind, pos in picks:
            alt = second_choice(own[pos], tops[pos])
            if alt is None:
                continue
            prefix = [*own[:pos], alt]
            c = post("/v1/completions", {"model": served, "prompt": prompt + prefix, "max_tokens": 768,
                                         "temperature": 0.0})["choices"][0]
            text = detok(served, prefix) + c["text"]
            s = task.score(item, Completion(text, "", None, None, 0, 0, c["finish_reason"]), 20)
            out.append({"kind": kind, "position": pos, "own_logprob": chosen[pos],
                        "alt_logprob": tops[pos].get(f"token_id:{alt}"), "passed": s["passed"], "status": s["status"]})
        return out

    start = time.time()
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(walk, jobs))
    with (WORK / "walks.jsonl").open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    rescued = sum(r["passed"] for r in rows)
    nudged = [c["passed"] for r in rows for c in r["controls"]]
    log(f"walks: {rescued}/{len(rows)} pass within {MAX_FORCED} forced tokens; control nudges "
        f"{sum(nudged)}/{len(nudged)} pass; {time.time() - start:.0f}s")


def main() -> None:
    setup()
    isolation = score_in_isolation()
    adapters = adapter_paths()
    log(f"adapters {adapters}; network isolation {isolation}")
    cmd = [str(VLLM_VENV / "bin" / "vllm"), "serve", BASE[0], "--revision", BASE[1], "--served-model-name", "local",
           "--port", str(PORT), "--dtype", "half", "--max-model-len", "4096", "--gpu-memory-utilization", "0.90",
           "--enforce-eager", "--seed", "3407", "--enable-lora", "--max-lora-rank", "16", "--max-loras", "2",
           "--max-logprobs", "5", "--lora-modules", *(f"{name}={path}" for name, path in adapters.items())]
    with open(LOGS / "vllm.log", "w") as fh:
        server = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"})
    try:
        if not wait_healthy(server):
            raise RuntimeError("server failed to start, see logs/vllm.log")
        log("server ready")
        walks()
    finally:
        server.terminate()
        try:
            server.wait(timeout=120)
        except subprocess.TimeoutExpired:
            server.kill()
    log("all done")


if __name__ == "__main__":
    main()
