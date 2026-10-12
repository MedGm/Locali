"""Pull Python code out of a model response and sanitize it before execution."""

import ast
import re

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE = re.compile(r"```[ \t]*(?:python|py|python3)?[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)
# Opening fence never closed, e.g. an answer cut off at the token limit.
_OPEN_FENCE = re.compile(r"```[ \t]*(?:python|py|python3)?[ \t]*\n(.*)$", re.DOTALL | re.IGNORECASE)


def extract_code(text: str, entry_point: str | None = None) -> str:
    """Return the most plausible code block.

    Order: a fenced block that defines `entry_point`, else the first fenced block,
    else the whole response. Reasoning inside <think> tags is ignored.
    """
    text = _THINK.sub("", text)
    blocks = [b.strip("\n") for b in _FENCE.findall(text)]
    if entry_point:
        defining = re.compile(rf"^\s*(async\s+)?def\s+{re.escape(entry_point)}\s*\(", re.MULTILINE)
        for block in blocks:
            if defining.search(block):
                return block
    if blocks:
        return blocks[0]
    unclosed = _OPEN_FENCE.search(text)
    if unclosed:
        return unclosed.group(1).strip("\n")
    return text.strip("\n")


_KEEP = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)


def sanitize(code: str) -> str:
    """Keep only definitions a solution needs: imports, functions, classes, global assignments.

    Mirrors the intent of EvalPlus' sanitizer: model-written top-level asserts, prints,
    example calls and `if __name__ == "__main__"` blocks are dropped, so a wrong self-test
    cannot fail a correct solution. A truncated tail is trimmed line by line until the code
    parses. Dropped statements are deleted line by line; everything kept keeps its original
    text and spacing, so formatting-sensitive metrics (lint) are not disturbed. Code that
    never parses, or keeps nothing, is returned unchanged.
    """
    lines = code.splitlines()
    for end in range(len(lines), 0, -1):
        try:
            tree = ast.parse("\n".join(lines[:end]))
        except SyntaxError:
            continue
        if not any(isinstance(node, _KEEP) for node in tree.body):
            return code
        dropped: set[int] = set()
        for node in tree.body:
            if not isinstance(node, _KEEP):
                start = min([d.lineno for d in getattr(node, "decorator_list", [])] + [node.lineno])
                dropped.update(range(start - 1, node.end_lineno))
        kept = [line for i, line in enumerate(lines[:end]) if i not in dropped]
        while kept and (not kept[-1].strip() or kept[-1].lstrip().startswith("#")):
            kept.pop()  # trailing blank lines and comments such as "# Test cases"
        while kept and not kept[0].strip():
            kept.pop(0)
        return "\n".join(kept)
    return code


def python_blocks(text: str) -> list[str]:
    """All Python (or unlabelled) fenced blocks in order, plus a trailing unclosed one."""
    text = _THINK.sub("", text)
    blocks, end = [], 0
    for match in _FENCE.finditer(text):
        blocks.append(match.group(1).strip("\n"))
        end = match.end()
    unclosed = _OPEN_FENCE.search(text, end)
    if unclosed:
        blocks.append(unclosed.group(1).strip("\n"))
    return [b for b in blocks if b.strip()]


def extract_all_code(text: str) -> str:
    """Join every Python block: for answers that split one file over several blocks."""
    blocks = python_blocks(text)
    return "\n\n".join(blocks) if blocks else extract_code(text)


def trim_to_parseable(code: str) -> str:
    """Drop lines from the end until the code parses; keep every complete statement."""
    lines = code.splitlines()
    for end in range(len(lines), 0, -1):
        candidate = "\n".join(lines[:end]).rstrip()
        try:
            ast.parse(candidate)
        except SyntaxError:
            continue
        return candidate
    return code
