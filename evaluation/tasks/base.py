"""Interface every benchmark task implements so one runner can drive all of them."""

from typing import Any, Protocol

from evaluation.client import Completion


class Task(Protocol):
    name: str
    dataset: tuple[str, str] | None  # (Hugging Face repo, pinned revision)

    @property
    def excluded(self) -> dict[str, str]:
        """task_id -> reason, for items removed after harness validation."""

    def load(self, limit: int | None = None) -> list[Any]:
        """Items to evaluate; each has a unique `task_id`."""

    def messages(self, item: Any) -> list[dict]:
        """Chat messages sent to the model."""

    def score(self, item: Any, completion: Completion, eval_timeout_s: float) -> dict:
        """Per-item result fields; must include `status`."""

    def metrics(self, records: list[dict]) -> dict:
        """Task-specific aggregate metrics over all records."""

    def reference(self, item: Any) -> str:
        """A known-correct model answer, used to validate the harness."""
