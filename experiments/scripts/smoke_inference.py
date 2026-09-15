"""Smoke test for an OpenAI-compatible endpoint: one streamed completion, TTFT and speed.

Usage:
    uv run python experiments/scripts/smoke_inference.py --base-url http://127.0.0.1:8080/v1
"""

import argparse
import json
import time
import urllib.request

PROMPT = (
    "Write a Python function `is_palindrome(s: str) -> bool` that ignores case and "
    "non-alphanumeric characters. Return only the code."
)


def run(base_url: str, model: str, max_tokens: int) -> dict:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
    )

    start = time.perf_counter()
    ttft = None
    text = []
    usage = {}
    timings = {}
    with urllib.request.urlopen(req) as resp:
        for raw in resp:
            line = raw.decode().strip()
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            chunk = json.loads(line[6:])
            for choice in chunk.get("choices", []):
                delta = choice.get("delta", {}).get("content")
                if delta:
                    if ttft is None:
                        ttft = time.perf_counter() - start
                    text.append(delta)
            usage = chunk.get("usage") or usage
            timings = chunk.get("timings") or timings  # llama.cpp server extension
    total = time.perf_counter() - start

    return {
        "model": model,
        "ttft_ms": round((ttft or total) * 1000),
        "total_s": round(total, 2),
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "prompt_tok_per_s": round(timings.get("prompt_per_second", 0), 1) or None,
        "gen_tok_per_s": round(timings.get("predicted_per_second", 0), 1) or None,
        "output": "".join(text),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", default="local")
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()

    result = run(args.base_url, args.model, args.max_tokens)
    output = result.pop("output")
    print(output)
    print("-" * 60)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
