import json
import shutil
import subprocess
from dataclasses import replace

import pytest

from evaluation.client import Completion
from evaluation.run import RunConfig, run_benchmark
from evaluation.tasks.codegen import HUMANEVAL_PLUS_TASK
from evaluation.tests.test_codegen import HUMANEVAL_STYLE

pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None
    or subprocess.run(["docker", "info"], capture_output=True, check=False).returncode != 0,
    reason="Docker daemon not available",
)

GOOD = "```python\ndef circle_area(r):\n    return math.pi * r * r\n```"
BAD = "```python\ndef circle_area(r):\n    return r\n```"


def fake_generate(answers: dict[str, tuple[str, str]]):
    def generate(problem):
        text, finish = answers[problem.task_id]
        return Completion(text=text, reasoning="", input_tokens=50, output_tokens=20,
                          ttft_s=0.5, total_s=2.5, finish_reason=finish)
    return generate


@pytest.fixture
def config():
    return RunConfig(benchmark="toy", model_id="fake-model", runtime="test", max_tokens=64)


def run_two(tmp_path, config):
    problems = [replace(HUMANEVAL_STYLE, task_id="toy/good"), replace(HUMANEVAL_STYLE, task_id="toy/bad")]
    generate = fake_generate({"toy/good": (GOOD, "stop"), "toy/bad": (BAD, "length")})
    return run_benchmark(config, HUMANEVAL_PLUS_TASK, problems, generate, tmp_path / "out")


def test_summary_reports_pass_at_1_and_status_counts(tmp_path, config):
    summary = run_two(tmp_path, config)

    assert summary["metrics"]["pass@1"] == 0.5
    assert summary["metrics"]["status_counts"] == {"passed": 1, "failed": 1}
    assert summary["metrics"]["truncated"] == 1


def test_summary_reports_efficiency_metrics(tmp_path, config):
    summary = run_two(tmp_path, config)

    m = summary["metrics"]
    assert m["mean_ttft_s"] == 0.5
    assert m["mean_output_tokens"] == 20
    assert m["mean_decode_tok_per_s"] == pytest.approx(20 / 2.0)


def test_writes_one_sample_record_per_problem(tmp_path, config):
    run_two(tmp_path, config)

    lines = (tmp_path / "out" / "samples.jsonl").read_text().splitlines()
    records = {json.loads(line)["task_id"]: json.loads(line) for line in lines}
    assert set(records) == {"toy/good", "toy/bad"}
    assert records["toy/good"]["status"] == "passed"
    assert "def circle_area" in records["toy/bad"]["code"]


def test_summary_records_config_and_environment(tmp_path, config):
    run_two(tmp_path, config)

    saved = json.loads((tmp_path / "out" / "summary.json").read_text())
    assert saved["config"]["model_id"] == "fake-model"
    assert len(saved["environment"]["git_commit"]) == 40
    assert saved["environment"]["cpu"]
    assert "started_at" in saved["environment"]


def test_resumes_without_regenerating_recorded_problems(tmp_path, config):
    out = tmp_path / "out"
    out.mkdir()
    recorded = {"task_id": "toy/good", "status": "passed", "passed": True, "input_tokens": 50,
                "output_tokens": 20, "ttft_s": 0.5, "total_s": 2.5, "finish_reason": "stop",
                "energy_j": None, "code": "...", "completion": "...", "reasoning": "", "eval_duration_s": 1.0}
    (out / "samples.jsonl").write_text(json.dumps(recorded) + "\n")
    problems = [replace(HUMANEVAL_STYLE, task_id="toy/good"), replace(HUMANEVAL_STYLE, task_id="toy/bad")]
    asked = []

    def generate(problem):
        asked.append(problem.task_id)
        return Completion(BAD, "", 50, 20, 0.5, 2.5, "stop")

    summary = run_benchmark(config, HUMANEVAL_PLUS_TASK, problems, generate, out)

    assert asked == ["toy/bad"]
    assert summary["metrics"]["n"] == 2


def test_default_eval_timeout_fits_slowest_reference_solution():
    # Mbpp/599's reference needs ~37 s on one sandbox CPU (harness validation, 2026-09-15).
    assert RunConfig(benchmark="x", model_id="x", runtime="x", max_tokens=1).eval_timeout_s >= 60


def test_summary_lists_excluded_problems_for_the_benchmark(tmp_path):
    config = RunConfig(benchmark="humaneval_plus", model_id="fake-model", runtime="test", max_tokens=64)
    problems = [replace(HUMANEVAL_STYLE, task_id="toy/good")]

    summary = run_benchmark(
        config, HUMANEVAL_PLUS_TASK, problems, fake_generate({"toy/good": (GOOD, "stop")}), tmp_path / "out"
    )

    assert list(summary["excluded"]) == ["HumanEval/32"]


def test_runner_registers_all_benchmark_tasks():
    from evaluation.run import TASKS

    assert {"humaneval_plus", "mbpp_plus", "humanevalfix", "bugdetect", "cruxeval_o", "testgen", "refactor"} <= set(TASKS)
