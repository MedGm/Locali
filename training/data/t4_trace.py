"""T4 execution-trace data: predict what a call returns (counters the CRUXEval drop of QLoRA v1).

Source: the CodeRM-UnitTest functions used for T1/T2. Inputs come from the problem's own unittest
suite: in a test method, literal assignments (`arr = [5, 10]`) are inlined into the call of
`self.assertEqual(<call of a solution function>, <literal>)`, so every call has literal arguments
only. The call is then executed in the sandbox and kept only if the traced return value equals the
literal the test expects: two independent sources agree on every label.

The prompt is our own wording with an `assert <call> == <value>` answer. It deliberately does not
reuse the CRUXEval template or its few-shot examples, so a CRUXEval gain reflects the skill rather
than a memorised prompt.
"""

import ast
import copy
import json
import re
import tempfile
from pathlib import Path

from security.sandbox import run_pytest
from training.data.t1_bugs import SOURCE, Seed

MAX_CALL_CHARS = 250
MAX_OUTPUT_CHARS = 120
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_TRACE = re.compile(r"LOCALI_TRACE (\[.*\])")


def _is_literal(node: ast.AST) -> bool:
    try:
        ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return False
    return True


class _Inline(ast.NodeTransformer):
    def __init__(self, env: dict[str, ast.AST]):
        self.env = env

    def visit_Name(self, node: ast.Name) -> ast.AST:
        return copy.deepcopy(self.env[node.id]) if node.id in self.env else node


def call_cases(code: str, tests: str) -> list[tuple[str, str]]:
    """(call source, expected literal source) pairs from assertEqual calls with literal inputs."""
    try:
        functions = {n.name for n in ast.parse(code).body if isinstance(n, ast.FunctionDef)}
        suite = ast.parse(tests)
    except SyntaxError:
        return []
    cases = []
    for method in ast.walk(suite):
        if not (isinstance(method, ast.FunctionDef) and method.name.startswith("test")):
            continue
        env: dict[str, ast.AST] = {}  # name -> literal, or a call of a solution function (`result = f(x)`)
        for stmt in method.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                name, value = stmt.targets[0].id, stmt.value
                if _is_literal(value):
                    env[name] = value
                elif isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id in functions:
                    env[name] = _Inline(env).visit(copy.deepcopy(value))
                else:
                    env.pop(name, None)
                continue
            if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
                continue
            call = stmt.value
            if not (isinstance(call.func, ast.Attribute) and call.func.attr == "assertEqual" and len(call.args) == 2):
                continue
            target, expected = (_Inline(env).visit(copy.deepcopy(a)) if isinstance(a, ast.Name) else a for a in call.args)
            if not (isinstance(target, ast.Call) and isinstance(target.func, ast.Name) and target.func.id in functions):
                continue
            inlined = _Inline(env).visit(copy.deepcopy(target))
            arguments = [*inlined.args, *(k.value for k in inlined.keywords)]
            if all(_is_literal(a) for a in arguments) and _is_literal(expected):
                cases.append((ast.unparse(inlined), ast.unparse(expected)))
    return list(dict.fromkeys(cases))


def _plain_value(value) -> bool:
    """No floats with long expansions (unpredictable rounding digits), recursively."""
    if isinstance(value, float):
        return len(repr(value)) <= 8
    if isinstance(value, (list, tuple, set, frozenset)):
        return all(_plain_value(v) for v in value)
    if isinstance(value, dict):
        return all(_plain_value(k) and _plain_value(v) for k, v in value.items())
    return True


def _trace(code: str, calls: list[str], timeout_s: float) -> list[str | None] | None:
    """repr of each call's return value (None if it raised), or None if the run failed."""
    test = (
        "import json\nfrom solution import *\n\n"
        f"CALLS = {calls!r}\n\n\n"
        "def test_trace():\n"
        "    out = []\n"
        "    for c in CALLS:\n"
        "        try:\n"
        "            out.append(repr(eval(c)))\n"
        "        except Exception:\n"
        "            out.append(None)\n"
        '    raise AssertionError("LOCALI_TRACE " + json.dumps(out))\n'
    )
    with tempfile.TemporaryDirectory(prefix="locali-t4-") as tmp:
        Path(tmp, "solution.py").write_text(code)
        Path(tmp, "test_trace.py").write_text(test)
        result = run_pytest(Path(tmp), timeout_s=timeout_s, coverage=False)
    match = _TRACE.search(result.output)
    if result.timed_out or not match:
        return None
    traced = json.loads(match.group(1))
    return traced if len(traced) == len(calls) else None


def trace_seed(seed: Seed, max_calls: int = 1, timeout_s: float = 30) -> list[dict]:
    cases = [(c, e) for c, e in call_cases(seed.code, seed.tests) if len(c) <= MAX_CALL_CHARS]
    if not cases:
        return []
    traced = _trace(seed.code, [c for c, _ in cases], timeout_s)
    examples = []
    for (call, expected), value in zip(cases, traced or [], strict=False):
        if value is None or len(value) > MAX_OUTPUT_CHARS:
            continue
        try:
            got = ast.literal_eval(value)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            continue  # not a literal (e.g. an object repr)
        if got != ast.literal_eval(expected) or type(got) is not type(ast.literal_eval(expected)) or not _plain_value(got):
            continue
        examples.append({"id": f"t4-{seed.task_id}-{len(examples)}", "source": f"{SOURCE}:{seed.task_id}",
                         "license": "Apache-2.0", "code": seed.code, "call": call, "output": value})
        if len(examples) >= max_calls:
            break
    return examples


def trace_prompt(code: str, call: str) -> str:
    return (
        "Predict the exact value returned by the call below, by tracing the code by hand.\n\n"
        f"```python\n{code.rstrip()}\n```\n\n"
        f"Call: `{call}`\n\n"
        f"Respond with one line: assert {call} == <the returned value as a Python literal>"
    )


def t4_messages(example: dict) -> list[dict]:
    return [
        {"role": "user", "content": trace_prompt(example["code"], example["call"])},
        {"role": "assistant", "content": f"assert {example['call']} == {example['output']}"},
    ]


def parse_trace_answer(text: str) -> str | None:
    """Source of the predicted value from the last `assert <call> == <value>` line."""
    text = re.sub(r"```[a-zA-Z]*", "", _THINK.sub("", text))
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("assert ") or "==" not in line:
            continue
        try:
            node = ast.parse(line).body[0]
        except SyntaxError:
            return line.split("==", 1)[1].strip()
        if isinstance(node.test, ast.Compare) and isinstance(node.test.ops[0], ast.Eq):
            return ast.unparse(node.test.comparators[-1])
    return None
