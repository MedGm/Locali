"""Context ablations of in-distribution bug repair (internal_t1), for C5 (context and token reduction).

Same held-out items and scoring as internal_t1; only the prompt changes:

- internal_t1_fullctx: the problem's whole unit-test suite replaces the single failing test
  (more context, more tokens). The failing test's name and error stay.
- internal_t1_compressed: comments, docstrings and blank lines are removed from the buggy function
  and the failing test (fewer tokens, same information for the fix).

The trained prompt is rebuilt with training.data.format.repair_prompt; parsing and rebuilding
reproduces all 212 test prompts byte for byte (tested), so only the intended part changes.
"""

import ast
import io
import re
import tokenize

from evaluation.tasks.internal import InternalItem, InternalRepairTask
from training.data.format import repair_prompt

_PROMPT = re.compile(
    r"The following Python function has a bug\.\n\n```python\n(?P<buggy_code>.*?)\n```\n\n"
    r"This test fails: `(?P<test_name>[^`]*)`\n```python\n(?P<test_code>.*?)\n```\n"
    r"Error:\n```\n(?P<error>.*?)\n```\n\n",
    re.DOTALL,
)


def parse_repair_prompt(prompt: str) -> dict[str, str]:
    match = _PROMPT.match(prompt)
    if not match:
        raise ValueError("not a T1 repair prompt")
    return match.groupdict()


def _docstring_lines(src: str) -> set[int]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    lines = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or len(body) < 2:  # a lone docstring keeps the body valid
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            lines.update(range(first.lineno, first.end_lineno + 1))
    return lines


def compress_python(src: str) -> str:
    """Remove comments, docstrings (where the body has other statements) and blank lines."""
    lines = src.splitlines()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                row, col = tok.start
                lines[row - 1] = lines[row - 1][:col]
    except (tokenize.TokenError, IndentationError):
        pass
    skip = _docstring_lines(src)
    kept = [line.rstrip() for i, line in enumerate(lines, 1) if i not in skip]
    return "\n".join(line for line in kept if line.strip())


class _RepairVariant(InternalRepairTask):
    def rewrite(self, item: InternalItem, parts: dict[str, str]) -> dict[str, str]:
        raise NotImplementedError

    def messages(self, item: InternalItem) -> list[dict]:
        parts = self.rewrite(item, parse_repair_prompt(item.messages[0]["content"]))
        return [{"role": "user", "content": repair_prompt(**parts)}]


class FullContextRepairTask(_RepairVariant):
    name = "internal_t1_fullctx"

    def rewrite(self, item, parts):
        return {**parts, "test_code": self._suite(item.group) or parts["test_code"]}


class CompressedRepairTask(_RepairVariant):
    name = "internal_t1_compressed"

    def rewrite(self, item, parts):
        return {**parts, "buggy_code": compress_python(parts["buggy_code"]),
                "test_code": compress_python(parts["test_code"])}


FULL_CONTEXT_REPAIR_TASK = FullContextRepairTask()
COMPRESSED_REPAIR_TASK = CompressedRepairTask()
