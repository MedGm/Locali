import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from evaluation.client import ChatClient


def sse(obj) -> bytes:
    return f"data: {json.dumps(obj)}\n\n".encode()


def delta(content=None, reasoning=None, finish=None):
    d = {}
    if content is not None:
        d["content"] = content
    if reasoning is not None:
        d["reasoning_content"] = reasoning
    return {"choices": [{"index": 0, "delta": d, "finish_reason": finish}]}


@pytest.fixture
def fake_server():
    """OpenAI-compatible streaming endpoint. Configure `script` before calling the client."""
    state = {"requests": [], "script": [], "first_delay": 0.0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(body)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            time.sleep(state["first_delay"])
            for event in state["script"]:
                self.wfile.write(sse(event))
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state["base_url"] = f"http://127.0.0.1:{server.server_address[1]}/v1"
    yield state
    server.shutdown()


USAGE = {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 3}}


def test_returns_text_and_token_usage(fake_server):
    fake_server["script"] = [delta("def "), delta("f(): "), delta("pass", finish="stop"), USAGE]

    out = ChatClient(fake_server["base_url"]).complete([{"role": "user", "content": "hi"}], max_tokens=16)

    assert out.text == "def f(): pass"
    assert (out.input_tokens, out.output_tokens) == (12, 3)
    assert out.finish_reason == "stop"


def test_measures_time_to_first_token(fake_server):
    fake_server["first_delay"] = 0.3
    fake_server["script"] = [delta("a"), delta("b", finish="stop"), USAGE]

    out = ChatClient(fake_server["base_url"]).complete([{"role": "user", "content": "hi"}], max_tokens=4)

    assert out.ttft_s >= 0.3
    assert out.total_s >= out.ttft_s


def test_sends_generation_settings_and_extra_body(fake_server):
    fake_server["script"] = [delta("x", finish="stop"), USAGE]
    client = ChatClient(fake_server["base_url"], extra_body={"chat_template_kwargs": {"enable_thinking": False}})

    client.complete([{"role": "user", "content": "hi"}], max_tokens=64, temperature=0.2, seed=7)

    sent = fake_server["requests"][0]
    assert sent["max_tokens"] == 64 and sent["temperature"] == 0.2 and sent["seed"] == 7
    assert sent["stream"] is True
    assert sent["chat_template_kwargs"] == {"enable_thinking": False}


def test_keeps_reasoning_separate_but_counts_it_for_ttft(fake_server):
    fake_server["script"] = [delta(reasoning="thinking..."), delta("answer", finish="stop"), USAGE]

    out = ChatClient(fake_server["base_url"]).complete([{"role": "user", "content": "hi"}], max_tokens=16)

    assert out.text == "answer"
    assert out.reasoning == "thinking..."
    assert out.ttft_s <= out.total_s


def test_reports_truncation(fake_server):
    fake_server["script"] = [delta("partial", finish="length"), USAGE]

    out = ChatClient(fake_server["base_url"]).complete([{"role": "user", "content": "hi"}], max_tokens=1)

    assert out.finish_reason == "length"
