"""The single gate every model call of a run goes through.

It redacts secrets from the outgoing messages (whatever agent built them) and from the answer, and
records the call for the run's trajectory: step, prompt, answer, tokens and latency. A model may
return a plain string or an object with `text`, `input_tokens` and `output_tokens` (the chat client).
A caller may ask for a sampling temperature (the debug agent's retries); it is passed on and recorded.

Known limit: a function that contains a secret literal reaches the model with a placeholder, so a
fix for it comes back with the placeholder; patch validation then decides whether it still works.
"""

import inspect
import time
from collections.abc import Callable, Iterable

from security.secrets import redact

Model = Callable[[list[dict]], str]


def takes_temperature(model: Callable) -> bool:
    """Whether `model(messages, temperature=...)` is a valid call; scripted test models take messages only."""
    try:
        params = inspect.signature(model).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(p.name == "temperature" or p.kind is p.VAR_KEYWORD for p in params)


def guarded(model: Callable[[list[dict]], object], record: Callable[[dict], None],
            step: Callable[[], str], known: Iterable[str] = ()) -> Model:
    """known: secret values found in the repository, removed wherever they appear (security.secrets)."""
    known = frozenset(known)
    sampled = takes_temperature(model)

    def call(messages: list[dict], temperature: float | None = None) -> str:
        clean = [{**m, "content": redact(m["content"], known)} for m in messages]
        redactions = sum(c["content"].count("[REDACTED:") - m["content"].count("[REDACTED:")
                         for c, m in zip(clean, messages, strict=True))
        start = time.perf_counter()
        if not sampled:
            temperature = None
        reply = model(clean) if temperature is None else model(clean, temperature=temperature)
        latency = time.perf_counter() - start
        text = redact(reply if isinstance(reply, str) else reply.text, known)
        record({
            "step": step(),
            "prompt": clean[-1]["content"],
            "answer": text,
            "input_tokens": getattr(reply, "input_tokens", None),
            "output_tokens": getattr(reply, "output_tokens", None),
            "latency_s": round(latency, 3),
            "redactions": redactions,
            **({"temperature": temperature} if temperature is not None else {}),
        })
        return text

    return call
