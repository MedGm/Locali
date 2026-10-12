import json
from dataclasses import replace

from evaluation.rescore import rescore_run
from evaluation.tasks.codegen import HUMANEVAL_PLUS_TASK
from evaluation.tests.test_codegen import HUMANEVAL_STYLE, needs_docker

CORRECT_WITH_BAD_SELF_TEST = (
    "```python\ndef circle_area(r):\n    return math.pi * r * r\n\nassert circle_area(1) == 3\n```"
)


def write_old_run(run_dir):
    run_dir.mkdir()
    record = {
        "task_id": "toy/0", "status": "failed", "passed": False, "code": "old", "eval_duration_s": 1.0,
        "input_tokens": 50, "output_tokens": 20, "ttft_s": 0.5, "total_s": 2.5, "finish_reason": "stop",
        "energy_j": 10.0, "completion": CORRECT_WITH_BAD_SELF_TEST, "reasoning": "",
    }
    (run_dir / "samples.jsonl").write_text(json.dumps(record) + "\n")
    (run_dir / "summary.json").write_text(json.dumps({
        "config": {"benchmark": "humaneval_plus", "eval_timeout_s": 60},
        "environment": {"git_commit": "abc"},
        "metrics": {"n": 1, "pass@1": 0.0},
        "excluded": {},
    }))


@needs_docker
def test_rescore_applies_current_scoring_and_keeps_the_original(tmp_path):
    run = tmp_path / "run"
    write_old_run(run)

    summary = rescore_run(run, HUMANEVAL_PLUS_TASK, [replace(HUMANEVAL_STYLE, task_id="toy/0")])

    record = json.loads((run / "samples.jsonl").read_text())
    assert record["passed"] is True
    assert record["energy_j"] == 10.0  # generation measurements untouched
    assert summary["metrics"]["pass@1"] == 1.0
    assert summary["rescored"]["previous_metrics"]["pass@1"] == 0.0
    assert len(summary["rescored"]["harness_commit"]) == 40
    original = json.loads((run / "samples.original.jsonl").read_text())
    assert original["status"] == "failed"


@needs_docker
def test_rescoring_twice_keeps_the_first_original(tmp_path):
    run = tmp_path / "run"
    write_old_run(run)
    items = [replace(HUMANEVAL_STYLE, task_id="toy/0")]

    rescore_run(run, HUMANEVAL_PLUS_TASK, items)
    summary = rescore_run(run, HUMANEVAL_PLUS_TASK, items)

    assert json.loads((run / "samples.original.jsonl").read_text())["status"] == "failed"
    assert summary["rescored"]["previous_metrics"]["pass@1"] == 0.0
