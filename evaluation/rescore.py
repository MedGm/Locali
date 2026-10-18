"""Re-apply the current scoring to answers already generated, without calling the model again.

Generation measurements (tokens, timing, energy) are kept as recorded. The first time a run is
rescored its original samples are saved as samples.original.jsonl and the previous metrics are
stored in summary["rescored"], so every change of score stays auditable.

    uv run python -m evaluation.rescore experiments/results/baselines/mbpp_plus/<run>
"""

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from evaluation.client import Completion
from evaluation.run import TASKS, aggregate
from evaluation.tasks.base import Task

GENERATION_FIELDS = (
    "task_id", "input_tokens", "output_tokens", "ttft_s", "total_s", "finish_reason",
    "energy_j", "completion", "reasoning",
)
OPTIONAL_FIELDS = ("draft_n", "draft_n_accepted")  # only in runs with speculative decoding


def rescore_run(run_dir: Path, task: Task, items: list, workers: int = 4) -> dict:
    samples = run_dir / "samples.jsonl"
    original = run_dir / "samples.original.jsonl"
    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text())

    if not original.exists():
        original.write_text(samples.read_text())
    records = [json.loads(line) for line in original.read_text().splitlines() if line.strip()]
    by_id = {item.task_id: item for item in items}
    timeout = summary["config"].get("eval_timeout_s", 60)

    def rescore(record: dict) -> dict:
        completion = Completion(
            record["completion"], record.get("reasoning", ""), record.get("input_tokens"),
            record.get("output_tokens"), record.get("ttft_s", 0.0), record.get("total_s", 0.0),
            record.get("finish_reason"),
        )
        generation = {k: record.get(k) for k in GENERATION_FIELDS} | {k: record[k] for k in OPTIONAL_FIELDS if k in record}
        return {"task_id": record["task_id"], **task.score(by_id[record["task_id"]], completion, timeout),
                **generation}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rescored = list(pool.map(rescore, records))
    samples.write_text("".join(json.dumps(r) + "\n" for r in rescored))

    previous = summary.get("rescored", {}).get("previous_metrics", summary["metrics"])
    summary["metrics"] = {**aggregate(rescored), **task.metrics(rescored)}
    summary["rescored"] = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "harness_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
        ).stdout.strip(),
        "previous_metrics": previous,
    }
    summary_path.write_text(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dirs", nargs="+", type=Path)
    args = parser.parse_args()
    for run_dir in args.run_dirs:
        benchmark = json.loads((run_dir / "summary.json").read_text())["config"]["benchmark"]
        task = TASKS[benchmark]
        summary = rescore_run(run_dir, task, task.load())
        before = summary["rescored"]["previous_metrics"]
        changed = {k: (before.get(k), v) for k, v in summary["metrics"].items()
                   if isinstance(v, (int, float)) and before.get(k) != v}
        print(run_dir, json.dumps(changed))


if __name__ == "__main__":
    main()
