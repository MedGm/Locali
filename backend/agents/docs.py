"""Documentation agent: one-line docstrings for public functions and methods that have none.

The model sees the function and answers with a sentence. Its answer is only ever used as text: it is
cleaned (no quotes, no backslashes, one line), put inside a docstring, and the file is kept only if
the change is docstrings and nothing else: with every docstring removed, the new syntax tree must
equal the old one. A reply that tries to sneak code in breaks that check and is dropped.
"""

import ast
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from backend.agents.files import is_test_file, python_files
from security.secrets import redact

Model = Callable[[list[dict]], str]
FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass
class DocsResult:
    files: list[str] = field(default_factory=list)
    documented: list[tuple[str, str]] = field(default_factory=list)
    rejected: int = 0


def docs_prompt(source: str) -> str:
    return ("Write a one-line docstring for this Python function. Say what it does and what it returns, "
            "in plain words. Answer with the sentence only.\n\n```python\n" + source + "\n```")


def _targets(tree: ast.Module) -> list[tuple[str, ast.AST]]:
    found = []
    for node in tree.body:
        if isinstance(node, FUNCS):
            found.append((node.name, node))
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            found += [(f"{node.name}.{n.name}", n) for n in node.body if isinstance(n, FUNCS)]
    return [(name, n) for name, n in found if not name.split(".")[-1].startswith("_")]


def _find(tree: ast.Module, name: str) -> ast.AST:
    return next(n for qualified, n in _targets(tree) if qualified == name)


def undocumented_functions(root: str | Path) -> list[tuple[str, str]]:
    root = Path(root)
    found = []
    for path in python_files(root):
        rel = path.relative_to(root)
        if is_test_file(rel):
            continue
        tree = ast.parse(path.read_text())
        found += [(rel.as_posix(), name) for name, node in _targets(tree)
                  if ast.get_docstring(node) is None and node.body[0].lineno > node.lineno]
    return found


def clean_docstring(answer: str) -> str | None:
    text = re.sub(r"```\w*", "", answer).replace('"""', "").replace("'''", "")
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    line = " ".join(line.replace("\\", "/").replace('"', "'").split())[:200]
    return redact(line) or None


def insert_docstring(source: str, name: str, text: str) -> str:
    node = _find(ast.parse(source), name)
    first = node.body[0]
    if first.lineno == node.lineno:
        raise ValueError(f"{name} is written on one line")
    start = min([first.lineno, *(d.lineno for d in getattr(first, "decorator_list", []))])
    text = text.replace("\\", "/").replace('"', "'")
    lines = source.splitlines(keepends=True)
    lines.insert(start - 1, " " * first.col_offset + f'"""{text}"""\n')
    return "".join(lines)


def _without_docstrings(tree: ast.Module) -> str:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, *FUNCS)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.dump(tree)


def docstring_only_change(old: str, new: str) -> bool:
    try:
        return _without_docstrings(ast.parse(old)) == _without_docstrings(ast.parse(new))
    except SyntaxError:
        return False


def generate_docs(root: str | Path, model: Model, skip=(), limit: int | None = 10) -> DocsResult:
    """skip: (file, function) pairs to leave alone, such as functions with a suspected bug."""
    root = Path(root)
    result = DocsResult()
    for rel, name in undocumented_functions(root):
        if (rel, name) in skip or (rel, name.split(".")[0]) in skip:
            continue
        if limit is not None and len(result.documented) >= limit:
            break
        path = root / rel
        old = path.read_text()
        source = ast.get_source_segment(old, _find(ast.parse(old), name))
        text = clean_docstring(model([{"role": "user", "content": docs_prompt(redact(source))}]))
        new = insert_docstring(old, name, text) if text else None
        if new is None or not docstring_only_change(old, new):
            result.rejected += 1
            continue
        path.write_text(new)
        result.documented.append((rel, name))
        if rel not in result.files:
            result.files.append(rel)
    return result
