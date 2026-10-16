"""Log the recorded experiments into MLflow, so the dashboard holds the whole history.

    uv run python experiments/scripts/log_to_mlflow.py --uri sqlite:///data/mlflow.db
    uv run mlflow ui --backend-store-uri sqlite:///data/mlflow.db     # then open http://127.0.0.1:5000

Three experiments:
- "evaluations": one run per evaluation folder (task x model x runtime) with the score computed by
  the same outcome rules as the reports, mean tokens, latency and energy
- "training": one run per fine-tuning job with its settings, final numbers and loss curve
- "datasets": the fine-tuning mixtures with their counts and Hugging Face link

Runs are tagged with their source folder and skipped when already logged, so re-running only adds
new results.
"""

import argparse
import json
import sys
from pathlib import Path

import mlflow
from mlflow import MlflowClient

sys.path.insert(0, str(Path(__file__).parent))
from paired_compare import OUTCOME

R = Path(__file__).resolve().parents[2] / "experiments" / "results"
SKIP_PARTS = {"harness_validation"}  # reference-solution checks, not model runs


ARTIFACTS = Path(__file__).resolve().parents[2] / "data" / "mlartifacts"


def experiment(name: str) -> str:
    found = mlflow.get_experiment_by_name(name)
    return found.experiment_id if found else mlflow.create_experiment(
        name, artifact_location=(ARTIFACTS / name).as_uri())


def logged_sources(client: MlflowClient, experiment_id: str) -> set[str]:
    runs = client.search_runs([experiment_id], max_results=50000)
    return {r.data.tags.get("source") for r in runs}


def evaluations(client: MlflowClient) -> int:
    exp = experiment("evaluations")
    done = logged_sources(client, exp)
    count = 0
    for summary_path in sorted(R.glob("**/summary.json")):
        run_dir = summary_path.parent
        rel = run_dir.relative_to(R).as_posix()
        task = run_dir.parent.name
        if rel in done or task not in OUTCOME or SKIP_PARTS & set(run_dir.parts):
            continue
        s = json.loads(summary_path.read_text())
        cfg, m = s.get("config", {}), s.get("metrics", {})
        samples = [json.loads(line) for line in (run_dir / "samples.jsonl").read_text().splitlines() if line.strip()]
        score = sum(OUTCOME[task](r) for r in samples) / len(samples) * 100 if samples else None
        with mlflow.start_run(experiment_id=exp, run_name=f"{task} · {cfg.get('model_id', run_dir.name)}"):
            mlflow.set_tags({"source": rel, "study": run_dir.relative_to(R).parts[0]})
            mlflow.log_params({k: cfg.get(k) for k in ("model_id", "model_revision", "quantization", "runtime",
                                                        "max_tokens", "temperature", "seed") if k in cfg}
                              | {"task": task})
            metrics = {"score": score, "items": len(samples), "mean_input_tokens": m.get("mean_input_tokens"),
                       "mean_output_tokens": m.get("mean_output_tokens"), "mean_ttft_s": m.get("mean_ttft_s"),
                       "mean_total_s": m.get("mean_total_s"), "decode_tokens_per_s": m.get("mean_decode_tok_per_s"),
                       "cpu_energy_j_per_item": m.get("mean_energy_j_per_task"),
                       "gpu_energy_j_per_item": (s.get("gpu_energy") or {}).get("j_per_task")}
            mlflow.log_metrics({k: float(v) for k, v in metrics.items() if v is not None})
        count += 1
    return count


def training(client: MlflowClient) -> int:
    exp = experiment("training")
    done = logged_sources(client, exp)
    count = 0
    for report_path in sorted(R.glob("*/train_report.json")):
        rel = report_path.parent.relative_to(R).as_posix()
        if rel in done:
            continue
        rep = json.loads(report_path.read_text())
        with mlflow.start_run(experiment_id=exp, run_name=rel):
            mlflow.set_tags({"source": rel})
            mlflow.log_params({k: rep.get(k) for k in ("model", "method", "train_examples", "val_examples",
                                                        "dropped_too_long", "commit") if k in rep})
            mlflow.log_metrics({k: float(rep[k]) for k in ("train_loss", "train_seconds", "peak_memory_gb")
                                if rep.get(k) is not None})
            for entry in rep.get("log_history", []):
                if "loss" in entry and "step" in entry:
                    mlflow.log_metric("loss", float(entry["loss"]), step=int(entry["step"]))
        count += 1
    return count


def datasets(client: MlflowClient) -> int:
    exp = experiment("datasets")
    done = logged_sources(client, exp)
    count = 0
    for name, hf in (("data_mix_v1", None), ("data_mix_v2", "MedGm/locali-mix-v2")):
        stats_path = R / name / "stats.json"
        if not stats_path.exists() or name in done:
            continue
        stats = json.loads(stats_path.read_text())
        with mlflow.start_run(experiment_id=exp, run_name=name):
            mlflow.set_tags({"source": name, **({"huggingface": hf} if hf else {})})
            for split, tasks in stats["counts"].items():
                mlflow.log_metrics({f"{split}_{task}": float(n) for task, n in tasks.items()})
            mlflow.log_metric("total", float(stats["total"]))
            mlflow.log_dict(stats, "stats.json")
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="sqlite:///data/mlflow.db")
    args = parser.parse_args()
    mlflow.set_tracking_uri(args.uri)
    client = MlflowClient(args.uri)
    print(f"evaluations: {evaluations(client)} new, training: {training(client)} new, "
          f"datasets: {datasets(client)} new")


if __name__ == "__main__":
    main()
