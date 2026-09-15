"""Streaming client for OpenAI-compatible chat endpoints (llama.cpp server, vLLM).

Streaming is used so time-to-first-token can be measured on the client side.
"""

import json
import time
import urllib.request
from dataclasses import dataclass


@dataclass
class Completion:
    text: str
    reasoning: str
    input_tokens: int | None
    output_tokens: int | None
    ttft_s: float
    total_s: float
    finish_reason: str | None


class ChatClient:
    def __init__(
        self,
        base_url: str,
        *,
        model: str = "local",
        api_key: str = "local",
        extra_body: dict | None = None,
        timeout_s: float = 900,
    ):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.api_key = api_key
        self.extra_body = extra_body or {}
        self.timeout_s = timeout_s

    def complete(
        self,
        messages: list[dict],
        *,
        max_tokens: int,
        temperature: float = 0.0,
        seed: int | None = None,
    ) -> Completion:
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
            **({"seed": seed} if seed is not None else {}),
            **self.extra_body,
        }
        request = urllib.request.Request(
            self.url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )

        text, reasoning = [], []
        usage, finish_reason, first_token_at = {}, None, None
        start = time.perf_counter()
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            for raw in response:
                line = raw.decode().strip()
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                chunk = json.loads(line[6:])
                usage = chunk.get("usage") or usage
                for choice in chunk.get("choices", []):
                    d = choice.get("delta") or {}
                    piece = d.get("content")
                    thought = d.get("reasoning_content") or d.get("reasoning")
                    if (piece or thought) and first_token_at is None:
                        first_token_at = time.perf_counter()
                    if piece:
                        text.append(piece)
                    if thought:
                        reasoning.append(thought)
                    finish_reason = choice.get("finish_reason") or finish_reason
        end = time.perf_counter()

        return Completion(
            text="".join(text),
            reasoning="".join(reasoning),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            ttft_s=round((first_token_at or end) - start, 4),
            total_s=round(end - start, 4),
            finish_reason=finish_reason,
        )
