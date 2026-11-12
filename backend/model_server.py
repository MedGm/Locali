"""The playground's comparison model, picked on the page and started on demand.

The page lists every model of backend/models.json whose GGUF file is in the models folder. Picking
one stops the comparison server that is running (if any) and starts llama.cpp's server with the new
file on the comparison port. Only one comparison model runs at a time: two 3B models already take
about 4.5 GB of the laptop's 15 GB.

In models.json, "gguf" is the file name (or names: the build name, then the Hugging Face name) and
"label" the short name the app shows.

The server is started with --alias <model id>, so the backend can check that the server answering on
the port is the one it started and not something else left running there.
"""

import json
import os
import secrets
import socket
import threading
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from security import commands

# the free RAM a model needs on top of its file: context cache and buffers (measured: 3B Q4 file 1.9 GB, 2.2 GB RAM)
RAM_MARGIN_GIB = 0.6


class ModelServerError(RuntimeError):
    pass


def available_gib() -> float | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 2**20
    except OSError:
        pass
    return None


def _port_in_use(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _serving(url: str, key: str) -> str | None:
    """The model alias the server at url answers with, or None while it is not ready."""
    req = urllib.request.Request(f"{url}/models", headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            data = json.load(r).get("data") or []
    except (OSError, ValueError):
        return None
    return data[0].get("id") if data else None


class ModelServer:
    def __init__(self, registry: list[dict], models_dir: str | Path, port: int, binary: str | Path,
                 client: Callable[[str, str], Any], exclude: str | None = None, key: str | None = None,
                 log_file: str | Path | None = None, launch: Callable[..., Any] = commands.start_model_server,
                 serving: Callable[[str, str], str | None] = _serving, port_in_use: Callable[[int], bool] = _port_in_use,
                 free_gib: Callable[[], float | None] = available_gib, timeout_s: float = 180.0):
        """registry is the "models" list of models.json; client(url, key) returns the playground model
        that streams from a server; exclude is the assistant's own model, already on the page."""
        self.models_dir = Path(models_dir).expanduser()
        self.port, self.binary, self.client, self.exclude = port, str(binary), client, exclude
        self.key = key or secrets.token_hex(16)
        self.log_file = Path(log_file) if log_file else None
        self._launch, self._serving, self._port_in_use, self._free_gib = launch, serving, port_in_use, free_gib
        self.timeout_s = timeout_s
        self._registry = {m["id"]: m for m in registry if m.get("gguf")}
        self._lock = threading.Lock()
        self._process = None
        self.current: str | None = None
        self.starting: str | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def file(self, model_id: str) -> Path | None:
        """The model's GGUF file in the models folder: "gguf" is one name or several (build name, Hub name)."""
        names = self._registry[model_id]["gguf"]
        for name in [names] if isinstance(names, str) else names:
            if (self.models_dir / name).is_file():
                return self.models_dir / name
        return None

    def choices(self) -> list[dict]:
        return [{"id": m["id"], "name": m["name"], "size_gib": m.get("size_gib"), "fine_tuned": m.get("fine_tuned")}
                for m in self._registry.values() if m["id"] != self.exclude and self.file(m["id"])]

    def model(self):
        """The playground model of the running comparison server, or None."""
        return self.client(self.url, self.key) if self.current else None

    def start(self, model_id: str) -> None:
        if model_id not in {c["id"] for c in self.choices()}:
            raise KeyError(model_id)
        with self._lock:
            if self.current == model_id and self._alive():
                return
            self._stop()
            entry = self._registry[model_id]
            need = (entry.get("size_gib") or 0) + RAM_MARGIN_GIB
            free = self._free_gib()
            if free is not None and free < need:
                raise ModelServerError(f"{model_id} needs about {need:.1f} GB of free RAM, {free:.1f} GB is free")
            if self._port_in_use(self.port):
                raise ModelServerError(f"port {self.port} is used by another program; stop it first "
                                       "(an old 'scripts/run.sh compare'?)")
            self.starting = model_id
            try:
                self._process = self._launch(self._command(entry), log=self.log_file)
                self._wait(model_id)
            except BaseException:
                self._stop()
                raise
            finally:
                self.starting = None
            self.current = model_id

    def stop(self) -> None:
        with self._lock:
            self._stop()

    def _command(self, entry: dict) -> list[str]:
        cmd = [self.binary, "-m", str(self.file(entry["id"])), "--alias", entry["id"], "--jinja",
               "--parallel", "1", "--cache-ram", "0", "-c", "4096", "--host", "127.0.0.1",
               "--port", str(self.port), "--api-key", self.key]
        spec = os.environ.get("LOCALI_SPEC", "ngram-simple")  # same default as scripts/run.sh
        return cmd + (["--spec-type", spec] if spec != "none" else [])

    def _alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _wait(self, model_id: str) -> None:
        end = time.monotonic() + self.timeout_s
        while time.monotonic() < end:
            if not self._alive():
                where = f"; see {self.log_file}" if self.log_file else ""
                raise ModelServerError(f"the model server for {model_id} stopped while loading{where}")
            served = self._serving(self.url, self.key)
            if served == model_id:
                return
            if served is not None:
                raise ModelServerError(f"port {self.port} answers with {served!r}, not {model_id!r}")
            time.sleep(0.5)
        raise ModelServerError(f"{model_id} did not load within {self.timeout_s:.0f} s")

    def _stop(self) -> None:
        process, self._process, self.current = self._process, None, None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=10)
        except commands.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
