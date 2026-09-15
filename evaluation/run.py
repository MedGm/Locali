"""Run a code-generation benchmark against an OpenAI-compatible endpoint.

Writes <out>/samples.jsonl (one record per problem, appended as it finishes, so runs resume)
and <out>/summary.json (config, environment, aggregate metrics).

    # model under test (llama.cpp server or vLLM)
    uv run python -m evaluation.run --benchmark humaneval_plus --model-id qwen2.5-coder-1.5b \
        --quantization Q4_K_M --runtime llama.cpp --base-url http://127.0.0.1:8080/v1 \
        --out experiments/results/baselines/humaneval_plus/qwen2.5-coder-1.5b-q4km-cpu

    # harness validation: official reference solutions instead of a model
    uv run python -m evaluation.run --benchmark mbpp_plus --reference --out /tmp/ref-mbpp
"""

import argparse
import json
import platform
import statistics
import subprocess
import threading
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from evaluation.client import ChatClient, Completion
from evaluation.energy import RaplMeter
from evaluation.tasks.base import Task
from evaluation.tasks.codegen import HUMANEVAL_PLUS_TASK, MBPP_PLUS_TASK
from evaluation.tasks.completion import COMPLETION_TASK
from evaluation.tasks.cruxeval import CRUX_OUTPUT_TASK
from evaluation.tasks.humanevalpack import BUG_DETECT_TASK, FIX_TASK
from evaluation.tasks.refactor import REFACTOR_TASK
from evaluation.tasks.testgen import TESTGEN_TASK

TASKS: dict[str, Task] = {
    task.name: task for task in [HUMANEVAL_PLUS_TASK, MBPP_PLUS_TASK, FIX_TASK, BUG_DETECT_TASK, CRUX_OUTPUT_TASK, TESTGEN_TASK, REFACTOR_TASK, COMPLETION_TASK]
}


@dataclass
class RunConfig:
    benchmark: str
    model_id: str
    runtime: str
    max_tokens: int
    model_revision: str | None = None
    quantization: str | None = None
    base_url: str | None = None
    thinking: bool = False
    temperature: float = 0.0
    seed: int = 3407
    limit: int | None = None
    workers: int = 1
    eval_timeout_s: float = 60  # Mbpp/599 reference needs ~37 s
    prompt_variant: str = "evalplus-instruct"
    dataset: str | None = None
    dataset_revision: str | None = None
    notes: str = ""


def environment() -> dict:
    def run(cmd: list[str]) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout.strip()
        except OSError:
            return ""

    cpu = next(
        (line.split(":", 1)[1].strip() for line in _read_lines("/proc/cpuinfo") if line.startswith("model name")),
        platform.processor(),
    )
    mem_kb = next((int(line.split()[1]) for line in _read_lines("/proc/meminfo") if line.startswith("MemTotal")), 0)
    return {
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": run(["git", "rev-parse", "HEAD"]),
        "git_dirty": bool(run(["git", "status", "--porcelain"])),
        "host": platform.node(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu": cpu,
        "ram_gb": round(mem_kb / 2**20, 1),
        "gpus": [g for g in run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"]).splitlines() if g],
        "rapl_energy_available": RaplMeter().available,
    }


def _read_lines(path: str) -> list[str]:
    try:
        return Path(path).read_text().splitlines()
    except OSError:
        return []


def run_benchmark(
    config: RunConfig,
    task: Task,
    items: list,
    generate: Callable[[object], Completion],
    out_dir: Path,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    samples_path = out_dir / "samples.jsonl"
    done = {json.loads(line)["task_id"] for line in _read_lines(str(samples_path)) if line.strip()}
    todo = [item for item in items if item.task_id not in done]
    env = environment()
    meter = RaplMeter()
    lock = threading.Lock()

    def solve(item) -> None:
        with meter.measure() as energy:
            completion = generate(item)
        record = {
            "task_id": item.task_id,
            **task.score(item, completion, config.eval_timeout_s),
            "input_tokens": completion.input_tokens,
            "output_tokens": completion.output_tokens,
            "ttft_s": completion.ttft_s,
            "total_s": completion.total_s,
            "finish_reason": completion.finish_reason,
            # Per-call energy is only meaningful when calls do not overlap.
            "energy_j": energy.joules if config.workers == 1 else None,
            "completion": completion.text,
            "reasoning": completion.reasoning,
        }
        with lock, samples_path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")

    wall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=config.workers) as pool:
        list(pool.map(solve, todo))
    wall_s = time.perf_counter() - wall_start

    records = [json.loads(line) for line in _read_lines(str(samples_path)) if line.strip()]
    summary = {
        "config": asdict(config),
        "environment": env,
        "metrics": {**aggregate(records), **task.metrics(records)},
        "excluded": task.excluded,
        "this_session": {"generated": len(todo), "resumed": len(done), "wall_s": round(wall_s, 1)},
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def aggregate(records: list[dict]) -> dict:
    n = len(records)

    def mean(key: str) -> float | None:
        values = [r[key] for r in records if r.get(key) is not None]
        return round(statistics.fmean(values), 4) if values else None

    decode = [
        r["output_tokens"] / (r["total_s"] - r["ttft_s"])
        for r in records
        if r.get("output_tokens") and r["total_s"] > r["ttft_s"]
    ]
    energy = [r["energy_j"] for r in records if r.get("energy_j") is not None]
    return {
        "n": n,
        "status_counts": dict(Counter(r["status"] for r in records)),
        "truncated": sum(r.get("finish_reason") == "length" for r in records),
        "mean_input_tokens": mean("input_tokens"),
        "mean_output_tokens": mean("output_tokens"),
        "mean_ttft_s": mean("ttft_s"),
        "median_ttft_s": round(statistics.median(r["ttft_s"] for r in records), 4) if n else None,
        "mean_total_s": mean("total_s"),
        "mean_decode_tok_per_s": round(statistics.fmean(decode), 2) if decode else None,
        "total_energy_j": round(sum(energy), 1) if energy else None,
        "mean_energy_j_per_task": round(statistics.fmean(energy), 2) if energy else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--benchmark", choices=TASKS, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reference", action="store_true", help="evaluate official solutions (harness check)")
    parser.add_argument("--model-id", default="reference")
    parser.add_argument("--model-revision")
    parser.add_argument("--quantization")
    parser.add_argument("--runtime", default="none")
    parser.add_argument("--base-url")
    parser.add_argument("--thinking", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=768)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    task = TASKS[args.benchmark]
    dataset, dataset_revision = task.dataset or (None, None)
    config = RunConfig(
        benchmark=args.benchmark, model_id=args.model_id, runtime=args.runtime, max_tokens=args.max_tokens,
        model_revision=args.model_revision, quantization=args.quantization, base_url=args.base_url,
        thinking=args.thinking, temperature=args.temperature, limit=args.limit, workers=args.workers,
        dataset=dataset, dataset_revision=dataset_revision, notes=args.notes,
    )
    items = task.load(limit=args.limit)

    if args.reference:
        def generate(item) -> Completion:
            return Completion(task.reference(item), "", None, None, 0.0, 0.0, "stop")
    else:
        if not args.base_url:
            parser.error("--base-url is required unless --reference is set")
        client = ChatClient(args.base_url, extra_body={"chat_template_kwargs": {"enable_thinking": args.thinking}})

        def generate(item) -> Completion:
            return client.complete(
                task.messages(item), max_tokens=config.max_tokens,
                temperature=config.temperature, seed=config.seed,
            )

    summary = run_benchmark(config, task, items, generate, args.out)
    print(json.dumps({"metrics": summary["metrics"], "this_session": summary["this_session"]}, indent=2))


if __name__ == "__main__":
    main()
