import json
import threading
from datetime import UTC, datetime
from pathlib import Path


class AuditLog:
    """Append-only JSONL log of every action the backend takes."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, action: str, **fields) -> None:
        event = {"time": datetime.now(UTC).isoformat(timespec="seconds"), "action": action, **fields}
        with self._lock, self.path.open("a") as f:
            f.write(json.dumps(event) + "\n")
