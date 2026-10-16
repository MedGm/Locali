"""LLMOps: agent runs recorded in MLflow, as a run (parameters, metrics, artifacts) with a trace.

Off unless a tracking URI is given (LOCALI_MLFLOW_URI, e.g. sqlite:///data/mlflow.db). Each agent
run becomes one MLflow run in the "agent-runs" experiment, holding:

- parameters: repository, mode, model, whether static tools ran
- metrics: findings per category, suspects, fixes, patches, model calls, tokens, generation time,
  redactions
- artifacts: the report and the full trajectory (every model call)
- a trace: a root span for the run, one span per workflow step, one per model call with the prompt
  the model saw and its answer

The model-call spans sit inside the redaction guard (backend.agents.model), so traces only ever
hold redacted text. Browse with: mlflow ui --backend-store-uri <the same URI>
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

EXPERIMENT = "agent-runs"


class Tracker:
    def __init__(self, uri: str | None = None, artifacts: str | None = None):
        self.enabled = uri is not None
        self.uri = uri
        self.experiment_id = None
        if self.enabled:
            import mlflow

            mlflow.set_tracking_uri(uri)
            existing = mlflow.get_experiment_by_name(EXPERIMENT)
            location = Path(artifacts) if artifacts else Path("data") / "mlartifacts" / EXPERIMENT  # never ./mlruns
            self.experiment_id = existing.experiment_id if existing else mlflow.create_experiment(
                EXPERIMENT, artifact_location=location.resolve().as_uri())

    @contextmanager
    def agent_run(self, run_id: str, params: dict) -> Iterator[None]:
        if not self.enabled:
            yield
            return
        import mlflow
        from mlflow.entities import SpanType

        mlflow.set_tracking_uri(self.uri)
        with mlflow.start_run(experiment_id=self.experiment_id, run_name=run_id):
            mlflow.log_params(params)
            try:
                with mlflow.start_span(name="agent_run", span_type=SpanType.AGENT) as span:
                    span.set_inputs({"run_id": run_id, **params})
                    yield
            finally:
                mlflow.flush_trace_async_logging()  # traces are written asynchronously; store the run's now

    def step(self, name: str, fn: Callable[[], dict]) -> dict:
        if not self.enabled:
            return fn()
        import mlflow
        from mlflow.entities import SpanType

        with mlflow.start_span(name=name, span_type=SpanType.CHAIN) as span:
            span.set_inputs({"step": name})
            out = fn()
            span.set_outputs(out)
            return out

    def wrap_model(self, model: Callable[[list[dict]], object]) -> Callable[[list[dict]], object]:
        if not self.enabled:
            return model
        import mlflow
        from mlflow.entities import SpanType

        def call(messages: list[dict]):
            with mlflow.start_span(name="model_call", span_type=SpanType.CHAT_MODEL) as span:
                span.set_inputs({"prompt": messages[-1]["content"]})
                reply = model(messages)
                span.set_outputs({"answer": reply if isinstance(reply, str) else reply.text})
                for key in ("input_tokens", "output_tokens"):
                    if getattr(reply, key, None) is not None:
                        span.set_attribute(key, getattr(reply, key))
                return reply

        return call

    def finish(self, metrics: dict, report: str, trajectory: Path | None) -> None:
        if not self.enabled:
            return
        import mlflow

        mlflow.log_metrics({k: float(v) for k, v in metrics.items() if v is not None})
        mlflow.log_text(report, "report.md")
        if trajectory and trajectory.exists():
            mlflow.log_text(trajectory.read_text(), "trajectory.jsonl")
