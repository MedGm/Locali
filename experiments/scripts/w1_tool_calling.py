"""W1 check: do small local models emit correct tool calls for the MCP repo tools?

Measures only the first model turn: does it call a tool, the right tool, with the right path.

    uv run python experiments/scripts/w1_tool_calling.py --model-id qwen2.5-coder-1.5b \
        --base-url http://127.0.0.1:8080/v1
"""

import argparse
import asyncio
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI

REPO_FILES = {
    "README.md": "# Tiny calc\nA calculator library with a CLI entry point.\n",
    "pkg/calc.py": "def add(a, b):\n    return a - b\n\n\ndef mul(a, b):\n    return a * b\n",
    "pkg/strings.py": "import os\n\n\ndef shout(s):\n    return s.upper()\n\n\ndef run(cmd):\n    return os.system(cmd)\n",
    "app/main.py": "from pkg.calc import add\n\nif __name__ == '__main__':\n    print(add(2, 3))\n",
    "tests/test_calc.py": "from pkg.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
}

# (user request, expected tool, expected path argument or None)
TASKS = [
    ("Show me the contents of pkg/calc.py.", "read_file", "pkg/calc.py"),
    ("What files are in this repository?", "list_files", None),
    ("Is there a bug in the add function in pkg/calc.py?", "read_file", "pkg/calc.py"),
    ("Read the README and summarize it.", "read_file", "README.md"),
    ("Which tests exist for the calculator? They are in tests/test_calc.py.", "read_file", "tests/test_calc.py"),
    ("Explain what app/main.py does.", "read_file", "app/main.py"),
    ("List all the files so I can pick one to review.", "list_files", None),
    ("Review pkg/strings.py for security issues.", "read_file", "pkg/strings.py"),
    ("I don't know the file layout. Find where the project's entry point is.", "list_files", None),
    ("Open pkg/strings.py and tell me how many functions it defines.", "read_file", "pkg/strings.py"),
]

SYSTEM = (
    "You are a software engineering assistant with read-only access to a repository through tools. "
    "When you need repository contents, call a tool instead of guessing."
)


def normalize(path: str | None) -> str | None:
    return path.removeprefix("./").strip() if isinstance(path, str) else path


def lenient_call(text: str) -> dict | None:
    """Recover a tool call written as plain JSON (e.g. in a markdown fence) instead of the
    model's native tool-call format. Counts intent separately from format adherence."""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or "name" not in data:
        return None
    return {"name": data["name"], "args": data.get("arguments") or data.get("parameters") or {}}


async def run(base_url: str, model_id: str, thinking: bool) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name, body in REPO_FILES.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(body)

        client = MultiServerMCPClient({
            "repo": {
                "transport": "stdio",
                "command": sys.executable,
                "args": ["-m", "mcp_servers.repo_server", "--root", str(root)],
                "cwd": os.getcwd(),
            }
        })
        tools = await client.get_tools()
        llm = ChatOpenAI(
            base_url=base_url, api_key="local", model="local", temperature=0, max_tokens=256,
            extra_body={"chat_template_kwargs": {"enable_thinking": thinking}},
        ).bind_tools(tools)

        rows = []
        for request, want_tool, want_path in TASKS:
            start = time.perf_counter()
            msg = await llm.ainvoke([SystemMessage(SYSTEM), HumanMessage(request)])
            latency = time.perf_counter() - start
            call = msg.tool_calls[0] if msg.tool_calls else None
            got_path = normalize(call["args"].get("path")) if call else None
            loose = call or lenient_call(msg.content if isinstance(msg.content, str) else "")
            loose_path = normalize(loose["args"].get("path")) if loose else None
            rows.append({
                "request": request,
                "tool_called": call is not None,
                "tool": call["name"] if call else None,
                "args": call["args"] if call else None,
                "correct_tool": bool(call) and call["name"] == want_tool,
                "correct_args": bool(call) and call["name"] == want_tool and got_path == want_path,
                "lenient_tool": loose["name"] if loose else None,
                "lenient_correct": bool(loose) and loose["name"] == want_tool and loose_path == want_path,
                "hallucinated_tool": bool(loose) and loose["name"] not in {"read_file", "list_files"},
                "text_reply": None if call else (msg.content or "")[:300],
                "latency_s": round(latency, 2),
                "output_tokens": (msg.usage_metadata or {}).get("output_tokens"),
            })

    n = len(rows)
    return {
        "experiment": "w1_tool_calling",
        "date": time.strftime("%Y-%m-%d"),
        "model": model_id,
        "thinking": thinking,
        "runtime": "llama.cpp server --jinja, Q4_K_M, laptop CPU",
        "tasks": n,
        "tool_call_rate": sum(r["tool_called"] for r in rows) / n,
        "correct_tool_rate": sum(r["correct_tool"] for r in rows) / n,
        "correct_call_rate": sum(r["correct_args"] for r in rows) / n,
        "lenient_correct_call_rate": sum(r["lenient_correct"] for r in rows) / n,
        "hallucinated_tool_rate": sum(r["hallucinated_tool"] for r in rows) / n,
        "mean_latency_s": round(sum(r["latency_s"] for r in rows) / n, 2),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--thinking", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(run(args.base_url, args.model_id, args.thinking))
    out = Path("experiments/results") / f"w1_tool_calling_{args.model_id}.json"
    out.write_text(json.dumps(result, indent=2))
    summary = {k: v for k, v in result.items() if k != "rows"}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
