"""Pull Python code out of a model response and sanitize it before execution."""

import ast
import re

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE_LINE = re.compile(r"^\s*```+\s*([\w+#.-]*)\s*$")
_PYTHON_LANGS = {"python", "py", "python3"}


def _fenced_blocks(text: str) -> list[tuple[str, str]]:
    """(language, content) of every fenced block, parsed line by line.

    A fence line with a language always opens a block (closing any open one, as in markdown
    tutorials that wrap everything in ```markdown); a bare fence closes the open block, or opens an
    unlabelled one. A block still open at the end (answer cut off) is kept.
    """
    blocks: list[tuple[str, str]] = []
    lang, body = None, []
    for line in _THINK.sub("", text).splitlines():
        match = _FENCE_LINE.match(line)
        if not match:
            if lang is not None:
                body.append(line)
            continue
        label = match.group(1).lower()
        if lang is not None:
            blocks.append((lang, "\n".join(body).strip("\n")))
            lang, body = None, []
            if not label:
                continue  # bare fence closed the block
        lang = label
    if lang is not None:
        blocks.append((lang, "\n".join(body).strip("\n")))
    return blocks


def _parses(code: str) -> bool:
    try:
        ast.parse(code)
    except SyntaxError:
        return False
    return True


def python_blocks(text: str) -> list[str]:
    """Python blocks in order: labelled python/py, or unlabelled ones that look like code."""
    blocks = [(lang, body) for lang, body in _fenced_blocks(text) if body.strip()]
    if len(blocks) == 1 and blocks[0][0] in _PYTHON_LANGS | {""}:
        return [blocks[0][1]]  # a single block is taken even if cut off mid-statement
    return [body for lang, body in blocks if lang in _PYTHON_LANGS or (lang == "" and _parses(body))]


def extract_code(text: str, entry_point: str | None = None) -> str:
    """Return the most plausible code block.

    Order: a Python block that defines `entry_point`, else the first Python block, else the
    whole response. Reasoning inside <think> tags and non-Python blocks (bash, markdown) are
    ignored.
    """
    blocks = python_blocks(text)
    if entry_point:
        defining = re.compile(rf"^\s*(async\s+)?def\s+{re.escape(entry_point)}\s*\(", re.MULTILINE)
        for block in blocks:
            if defining.search(block):
                return block
    if blocks:
        return blocks[0]
    return _THINK.sub("", text).strip("\n")


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
