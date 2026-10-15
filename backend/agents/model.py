"""The single gate every model call of a run goes through.

It redacts secrets from the outgoing messages (whatever agent built them) and from the answer, and
records the call for the run's trajectory: step, prompt, answer, tokens and latency. A model may
return a plain string or an object with `text`, `input_tokens` and `output_tokens` (the chat client).

Known limit: a function that contains a secret literal reaches the model with a placeholder, so a
fix for it comes back with the placeholder; patch validation then decides whether it still works.
"""

import time
from collections.abc import Callable

from security.secrets import redact

Model = Callable[[list[dict]], str]


def guarded(model: Callable[[list[dict]], object], record: Callable[[dict], None],
            step: Callable[[], str]) -> Model:
    def call(messages: list[dict]) -> str:
        clean = [{**m, "content": redact(m["content"])} for m in messages]
        start = time.perf_counter()
        reply = model(clean)
        latency = time.perf_counter() - start
        text = redact(reply if isinstance(reply, str) else reply.text)
        record({
            "step": step(),
            "prompt": clean[-1]["content"],
            "answer": text,
            "input_tokens": getattr(reply, "input_tokens", None),
            "output_tokens": getattr(reply, "output_tokens", None),
            "latency_s": round(latency, 3),
        })
        return text

    return call
