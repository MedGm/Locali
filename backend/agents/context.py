"""How much code the model sees when the review and test-generation steps work on one function.

- file: the whole file (a review then covers every function of the file in one call)
- function: the function alone (the default)
- slice: the function plus the definitions, constants and imports it uses (backend.context_slice)
- compact: the function without its docstring, comment-only lines and blank lines

Findings are always located in the original function, so every setting reports the same lines.
"""

import ast
from pathlib import Path

from backend.context_slice import slice_function

CONTEXTS = ["file", "function", "slice", "compact"]


def _node(src: str, name: str) -> ast.FunctionDef:
    return next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == name)


def _compact(src: str, node: ast.FunctionDef) -> str:
    lines = src.splitlines()[node.lineno - 1:node.end_lineno]
    first = node.body[0]
    doc = set()
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        doc = set(range(first.lineno - node.lineno, first.end_lineno - node.lineno + 1))
    return "\n".join(line for i, line in enumerate(lines)
                     if i not in doc and line.strip() and not line.strip().startswith("#")) + "\n"


def function_context(root: str | Path, rel: str, name: str, context: str) -> str:
    src = (Path(root) / rel).read_text()
    if context == "file":
        return src
    if context == "slice":
        return slice_function(root, rel, name)
    node = _node(src, name)
    if context == "compact":
        return _compact(src, node)
    if context == "function":
        return ast.get_source_segment(src, node) + "\n"
    raise ValueError(f"unknown context {context!r}")
