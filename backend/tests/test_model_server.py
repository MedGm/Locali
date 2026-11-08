import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.model_server import ModelServer, ModelServerError
from evaluation.client import Completion

REGISTRY = [
    {"id": "ft3b-q4", "name": "run E", "gguf": "e.gguf", "size_gib": 1.8, "fine_tuned": True},
    {"id": "base3b-q4", "name": "base 3B", "gguf": "base.gguf", "size_gib": 2.0, "fine_tuned": False},
    {"id": "ft-q4", "name": "1.5B", "gguf": ["build-name.gguf", "small.gguf"], "size_gib": 0.9, "fine_tuned": True},
    {"id": "ft-f16", "name": "1.5B F16", "gguf": "missing.gguf", "size_gib": 2.9, "fine_tuned": True},
    {"id": "no-file", "name": "no gguf field"},
]


class FakeProcess:
    def __init__(self, cmd, dies=False):
        self.cmd, self.returncode = cmd, (1 if dies else None)
        self.alias = cmd[cmd.index("--alias") + 1]

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 0

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


def make(tmp_path, *, dies=False, foreign=None, busy=False, free=8.0):
    for name in ("e.gguf", "base.gguf", "small.gguf"):
        (tmp_path / name).write_bytes(b"")
    launched = []

    def launch(cmd, **_):
        launched.append(FakeProcess(cmd, dies))
        return launched[-1]

    def serving(url, key):
        if foreign:
            return foreign
        alive = [p for p in launched if p.poll() is None]
        return alive[-1].alias if alive else None

    server = ModelServer(REGISTRY, tmp_path, port=8094, binary="llama-server", exclude="ft3b-q4",
                         client=lambda url, key: ("client", url, key), launch=launch, serving=serving,
                         port_in_use=lambda port: busy, free_gib=lambda: free, timeout_s=1)
    return server, launched


def test_choices_are_the_models_on_disk_without_the_assistant_model(tmp_path):
    server, _ = make(tmp_path)
    assert [c["id"] for c in server.choices()] == ["base3b-q4", "ft-q4"]


def test_picking_a_model_starts_it_and_picking_another_stops_the_first(tmp_path):
    server, launched = make(tmp_path)
    server.start("base3b-q4")
    assert server.current == "base3b-q4" and len(launched) == 1
    cmd = launched[0].cmd
    assert cmd[cmd.index("-m") + 1] == str(tmp_path / "base.gguf") and cmd[cmd.index("--port") + 1] == "8094"
    assert server.model() == ("client", "http://127.0.0.1:8094/v1", server.key)
    server.start("base3b-q4")  # already running: nothing restarts
    assert len(launched) == 1
    server.start("ft-q4")
    assert launched[0].poll() is not None and server.current == "ft-q4"
    server.stop()
    assert server.current is None and server.model() is None and launched[1].poll() is not None


def test_unknown_or_missing_models_are_refused(tmp_path):
    server, launched = make(tmp_path)
    for model_id in ("ft-f16", "ft3b-q4", "nope"):
        with pytest.raises(KeyError):
            server.start(model_id)
    assert not launched


def test_a_server_that_dies_or_a_busy_port_or_low_ram_is_reported(tmp_path):
    server, _ = make(tmp_path, dies=True)
    with pytest.raises(ModelServerError, match="stopped while loading"):
        server.start("ft-q4")
    assert server.current is None and server.starting is None
    with pytest.raises(ModelServerError, match="port 8094"):
        make(tmp_path, busy=True)[0].start("ft-q4")
    with pytest.raises(ModelServerError, match="free RAM"):
        make(tmp_path, free=1.0)[0].start("base3b-q4")


def test_a_different_model_answering_on_the_port_is_not_taken_for_ours(tmp_path):
    server, launched = make(tmp_path, foreign="something-else")
    with pytest.raises(ModelServerError, match="something-else"):
        server.start("ft-q4")
    assert server.current is None and launched[0].poll() is not None


def test_the_api_lists_starts_and_uses_the_comparison_model(tmp_path):
    def stream(messages, on_token):
        on_token("ok")
        return Completion("ok", "", 3, 1, 0.01, 0.02, "stop")

    (tmp_path / "models").mkdir()
    server, _ = make(tmp_path / "models")
    server.client = lambda url, key: stream
    main = ("ft3b-q4", stream)
    client = TestClient(create_app(repos_root=tmp_path, data_dir=tmp_path / "data",
                                   playground={"main": main}, compare_server=server))
    state = client.get("/playground/compare").json()
    assert state["available"] and state["current"] is None
    assert [c["id"] for c in state["choices"]] == ["base3b-q4", "ft-q4"]
    assert client.get("/playground/models").json() == [{"key": "main", "id": "ft3b-q4"}]
    assert client.post("/playground/compare", json={"id": "ft-f16"}).status_code == 404
    assert client.post("/playground/compare", json={"id": "base3b-q4"}).json()["current"] == "base3b-q4"
    assert client.get("/playground/models").json()[1] == {"key": "compare", "id": "base3b-q4"}
    with client.stream("POST", "/playground", json={"task": "free", "prompt": "hi", "model": "compare"}) as r:
        assert '"model": "base3b-q4"' in "".join(r.iter_lines())
    assert client.post("/playground/compare", json={"id": None}).json()["current"] is None
    assert len(client.get("/playground/models").json()) == 1
    log = (tmp_path / "data" / "audit.jsonl").read_text()
    assert "playground.compare_started" in log and "playground.compare_stopped" in log


def test_without_a_models_folder_the_page_is_told_so(tmp_path):
    client = TestClient(create_app(repos_root=tmp_path, data_dir=tmp_path / "data"))
    assert client.get("/playground/compare").json()["available"] is False
    assert client.post("/playground/compare", json={"id": "ft-q4"}).status_code == 404
