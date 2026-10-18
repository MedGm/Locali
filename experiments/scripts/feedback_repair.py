"""Run HumanEvalFix (Python) with execution feedback against a model server; every fix runs in the sandbox.

    LOCALI_MODEL_KEY=... uv run python experiments/scripts/feedback_repair.py \\
        --base-url http://127.0.0.1:8093/v1 --model-id ft-q8 --out experiments/results/feedback_repair/ft-q8

Writes samples.jsonl (one row per problem, appended as it goes, so a stopped run resumes) and
summary.json: problems fixed after 1, 2 and 3 attempts. See evaluation/feedback_repair.py.

--explain: failing assertions report what the code returned and what was expected (the tests pass
exactly when the originals do). --retry-temperature T: attempts 2 and up are sampled at T instead
of greedy, so a retry is not a copy of the previous answer.
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evaluation.client import ChatClient
from evaluation.feedback_repair import explain_asserts, repair_with_feedback
from evaluation.tasks.codegen import run_program
from evaluation.tasks.humanevalpack import _import_lines, load_humanevalpack
from training.data.t1_bugs import failing_test_details


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--retry-temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=3407)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    client = ChatClient(args.base_url, api_key=os.environ.get("LOCALI_MODEL_KEY", "local"))
    tokens = {"input": 0, "output": 0}

    def model(messages, temperature=0.0):
        c = client.complete(messages, max_tokens=768, temperature=temperature, seed=args.seed)
        tokens["input"] += c.input_tokens or 0
        tokens["output"] += c.output_tokens or 0
        return c.text

    retry = (lambda messages: model(messages, args.retry_temperature)) if args.retry_temperature else None

    samples = args.out / "samples.jsonl"
    done = {json.loads(line)["task_id"] for line in samples.read_text().splitlines()} if samples.exists() else set()
    for item in load_humanevalpack(args.limit):
        if item.task_id in done:
            continue

        def run(code, item=item):
            test = explain_asserts(item.test) if args.explain else item.test
            program = f"{item.imports}\n{_import_lines(item.declaration)}\n{item.test_setup}\n\n{code}\n\n{test}\n"
            outcome = run_program(program, 60)
            if outcome.passed:
                return True, None
            _, error = failing_test_details(outcome.detail)
            return False, error or f"the tests {outcome.status}"

        row = repair_with_feedback(item, model, run, args.attempts, retry_model=retry) | {"bug_type": item.bug_type}
        with samples.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"{item.task_id}: {'fixed at attempt ' + str(row['fixed_at']) if row['fixed_at'] else 'not fixed'}",
              flush=True)

    rows = [json.loads(line) for line in samples.read_text().splitlines()]
    n = len(rows)
    within = {k: sum(r["fixed_at"] is not None and r["fixed_at"] <= k for r in rows) for k in range(1, args.attempts + 1)}
    summary = {"model_id": args.model_id, "n": n, "attempts": args.attempts, "explain": args.explain,
               "retry_temperature": args.retry_temperature,
               "fixed_within": {str(k): v for k, v in within.items()},
               "rate_within": {str(k): round(100 * v / n, 1) for k, v in within.items()},
               "model_calls": sum(r["attempts"] for r in rows), "tokens_this_session": tokens}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
